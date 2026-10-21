/*
 * usb-pd-card firmware
 *
 * Reads a USB-C charger's Source_Capabilities and shows them on the LEDs:
 * one LED per fixed voltage (5/9/12/15/20 V), PPS, EPR, and a 5-step wattage
 * bar. Only ever requests 5 V (PDO #1). A charger without PD blinks the 5V LED.
 *
 * The NFC tag and its LED (D2) are hardware only; nothing here touches them.
 */
#include "ch32fun.h"
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>

#ifndef PDCARD_LOG
#define PDCARD_LOG 0
#endif

#define USBPD_IMPLEMENTATION
#define USBPD_TRACE PDCARD_LOG // log builds record every PD message
#include "usbpd.h"

#ifndef PDCARD_CCDIAG
#define PDCARD_CCDIAG 0
#endif

#define LOG( fmt, ... ) \
	do { if ( PDCARD_LOG && DidDebuggerAttach() ) printf( fmt "\n", ##__VA_ARGS__ ); } while ( 0 )

// No Source_Capabilities by then: treat the charger as plain Type-C (no PD).
// Sources resend their caps every 100-200 ms for several seconds, so this is generous.
#define TYPEC_TIMEOUT_MS 1500

// LED pin map (AGENTS.md). Each LED: GPIO -> 1 kΩ -> LED -> GND, active high.
enum
{
	LED_5V, LED_9V, LED_12V, LED_15V, LED_20V, LED_PPS, LED_EPR,
	LED_15W, LED_30W, LED_45W, LED_65W, LED_100W,
	LED_COUNT
};
#define BIT( led ) ( 1u << ( led ) )

static const uint8_t s_ledPins[LED_COUNT] = {
	[LED_5V] = PA5,
	[LED_9V] = PA6,
	[LED_12V] = PA7,
	[LED_15V] = PB0,
	[LED_20V] = PB3,
	[LED_PPS] = PB4,
	[LED_EPR] = PB1, // PB1 shares pin 16 with PB5: never configure PB5
	[LED_15W] = PA4,
	[LED_30W] = PA3,
	[LED_45W] = PA2,
	[LED_65W] = PA1,
	[LED_100W] = PA0,
};

static const struct
{
	uint32_t mW;
	uint8_t led;
} s_wattBar[] = {
	{ 15000, LED_15W },
	{ 30000, LED_30W },
	{ 45000, LED_45W },
	{ 65000, LED_65W },
	{ 100000, LED_100W },
};

typedef enum
{
	eRP_NONE,
	eRP_DEFAULT, // default USB power (500/900 mA)
	eRP_1A5,
	eRP_3A0,
} RpLevel_e;

static volatile uint32_t s_ms = 0;

static void SysTick_Init( void );
static void LedsInit( void );
static void LedsShow( uint16_t mask );
static void LedsWalk( void );
static uint16_t CapsToLeds( const USBPD_SourcePDO_t *pdos, size_t count );
static RpLevel_e CCLevel( int cc );
static RpLevel_e MeasureRp( void );
#if PDCARD_CCDIAG
static void CCDiag( void );
#endif
#if PDCARD_LOG
static void LogCaps( const USBPD_SourcePDO_t *pdos, size_t count );
static bool TraceQuiet( void );
static void LogTrace( void );
#endif

int main( void )
{
	SystemInit();
	SysTick_Init();
	funGpioInitAll();

	LedsInit();
	LedsWalk();

	USBPD_Init( eUSBPD_VCC_3V3 );
	USBPD_Reset();

#if PDCARD_CCDIAG
	CCDiag();
#endif

	uint16_t shown = 0xffff;
	bool typecOnly = false;
	RpLevel_e rp = eRP_NONE;
	uint32_t lastLog = 0;

	while ( 1 )
	{
		// Polled: sends our Request as soon as the source's caps arrive (must be < ~25 ms)
		const USBPD_Result_e result = USBPD_SinkNegotiate();

		USBPD_SPR_CapabilitiesMessage_t *caps;
		const size_t count = USBPD_GetCapabilities( &caps );

		uint16_t leds = 0;
		if ( count > 0 )
		{
			leds = CapsToLeds( caps->Source, count );
		}
		else if ( s_ms >= TYPEC_TIMEOUT_MS )
		{
			if ( !typecOnly )
			{
				typecOnly = true;
				rp = MeasureRp();
			}
			// Blink 5V at 2 Hz; a 3 A Rp is 15 W at 5 V
			leds = ( ( s_ms / 250 ) & 1 ) ? BIT( LED_5V ) : 0;
			if ( rp == eRP_3A0 ) leds |= BIT( LED_15W );
		}

		if ( leds != shown )
		{
			LedsShow( leds );
			shown = leds;
		}

#if PDCARD_LOG
		// Print only while the CC line is quiet, so logging never delays a PD reply
		if ( TraceQuiet() ) LogTrace();
		if ( ( s_ms - lastLog ) > 2000 && TraceQuiet() )
		{
			lastLog = s_ms;
			if ( count > 0 )
			{
				LOG( "PD %d.0, %s", USBPD_GetVersion() + 1, eUSBPD_OK == result ? "contract at 5 V" : "negotiating" );
				LogCaps( caps->Source, count );
			}
			else if ( typecOnly )
			{
				LOG( "No PD, Type-C Rp level %d (1 default, 2 1.5 A, 3 3 A)", rp );
			}
		}
#else
		(void)result;
		(void)lastLog;
#endif
	}
}

static void LedsInit( void )
{
	for ( int i = 0; i < LED_COUNT; i++ )
	{
		funDigitalWrite( s_ledPins[i], FUN_LOW );
		funPinMode( s_ledPins[i], GPIO_CFGLR_OUT_10Mhz_PP );
	}
}

static void LedsShow( uint16_t mask )
{
	for ( int i = 0; i < LED_COUNT; i++ )
	{
		funDigitalWrite( s_ledPins[i], ( mask & BIT( i ) ) ? FUN_HIGH : FUN_LOW );
	}
}

// Power-on self test, ~250 ms. Runs before PD starts; the source just resends its caps.
static void LedsWalk( void )
{
	for ( int i = 0; i < LED_COUNT; i++ )
	{
		LedsShow( BIT( i ) );
		Delay_Ms( 20 );
	}
	LedsShow( 0 );
}

static uint16_t CapsToLeds( const USBPD_SourcePDO_t *pdos, size_t count )
{
	uint16_t leds = 0;
	uint32_t maxMW = 0;

	// EPR capability is a flag in the first (5 V) PDO; the EPR PDOs themselves
	// only appear after entering EPR mode, which we never do.
	if ( pdos[0].Header.PDOType == eUSBPD_PDO_FIXED && pdos[0].FixedSupply.EPRModeCapable )
	{
		leds |= BIT( LED_EPR );
	}

	for ( size_t i = 0; i < count; i++ )
	{
		const USBPD_SourcePDO_t *pdo = &pdos[i];
		uint32_t mV = 0;
		uint32_t mA = 0;

		if ( pdo->Header.PDOType == eUSBPD_PDO_FIXED )
		{
			mV = pdo->FixedSupply.VoltageIn50mV * 50;
			mA = pdo->FixedSupply.MaxCurrentIn10mA * 10;
			switch ( mV )
			{
				case 5000: leds |= BIT( LED_5V ); break;
				case 9000: leds |= BIT( LED_9V ); break;
				case 12000: leds |= BIT( LED_12V ); break;
				case 15000: leds |= BIT( LED_15V ); break;
				case 20000: leds |= BIT( LED_20V ); break;
				default: break;
			}
		}
		else if ( USBPD_IsPPS( pdo ) )
		{
			mV = pdo->SPR_PPS.MaxVoltageIn100mV * 100;
			mA = pdo->SPR_PPS.MaxCurrentIn50mA * 50;
			leds |= BIT( LED_PPS );
		}
		else if ( pdo->Header.PDOType == eUSBPD_PDO_AUGMENTED && pdo->Header.AugmentedType == eUSBPD_APDO_SPR_AVS )
		{
			mV = 20000;
			mA = pdo->SPR_AVS.MaxCurrent15To20VIn10mA * 10;
		}

		const uint32_t mW = mV * mA / 1000;
		if ( mW > maxMW ) maxMW = mW;
	}

	for ( size_t i = 0; i < sizeof( s_wattBar ) / sizeof( s_wattBar[0] ); i++ )
	{
		if ( maxMW >= s_wattBar[i].mW ) leds |= BIT( s_wattBar[i].led );
	}

	return leds;
}

// Rp level on one CC line (0 = CC1, 1 = CC2), from the CC voltage across our
// 5.1 kΩ Rd: default 0.25-0.61 V, 1.5 A 0.70-1.16 V, 3 A 1.31-2.04 V.
static RpLevel_e CCLevel( int cc )
{
	static const uint16_t thresholds[] = { CC_CMP_22, CC_CMP_66, CC_CMP_123 };
	const uint16_t config = USBPD->CONFIG;
	volatile uint16_t *port = cc ? &USBPD->PORT_CC2 : &USBPD->PORT_CC1;
	const uint16_t saved = *port;
	RpLevel_e level = eRP_NONE;

	if ( cc ) USBPD->CONFIG |= CC_SEL;
	else USBPD->CONFIG &= ~CC_SEL;

	for ( int t = 0; t < 3; t++ )
	{
		*port = ( saved & ~CC_CMP_MASK ) | thresholds[t];
		Delay_Us( 10 );
		if ( !( *port & PA_CC_AI ) ) break;
		level = (RpLevel_e)( t + 1 );
	}

	*port = saved;
	USBPD->CONFIG = config;
	return level;
}

// Rp current advertisement of a non-PD source: the higher of the two CC lines
static RpLevel_e MeasureRp( void )
{
	const RpLevel_e cc1 = CCLevel( 0 );
	const RpLevel_e cc2 = CCLevel( 1 );
	return cc1 > cc2 ? cc1 : cc2;
}

#if PDCARD_CCDIAG
// make CCDIAG=1: show what the MCU's CC comparators see, no PD.
// 9V/12V/15V = CC1 above 0.22/0.66/1.23 V, 20V/PPS/EPR = CC2 likewise, 5V blinks.
static void CCDiag( void )
{
	static const uint8_t cc1Leds[] = { LED_9V, LED_12V, LED_15V };
	static const uint8_t cc2Leds[] = { LED_20V, LED_PPS, LED_EPR };

	while ( 1 )
	{
		const RpLevel_e cc1 = CCLevel( 0 );
		const RpLevel_e cc2 = CCLevel( 1 );
		uint16_t leds = ( ( s_ms / 250 ) & 1 ) ? BIT( LED_5V ) : 0;

		for ( int i = 0; i < 3; i++ )
		{
			if ( cc1 > i ) leds |= BIT( cc1Leds[i] );
			if ( cc2 > i ) leds |= BIT( cc2Leds[i] );
		}
		LedsShow( leds );
		Delay_Ms( 20 );
	}
}
#endif

#if PDCARD_LOG
static void LogCaps( const USBPD_SourcePDO_t *pdos, size_t count )
{
	for ( size_t i = 0; i < count; i++ )
	{
		const USBPD_SourcePDO_t *pdo = &pdos[i];
		if ( pdo->Header.PDOType == eUSBPD_PDO_FIXED )
		{
			LOG( "  %d: fixed %d mV, %d mA%s", (int)i + 1, pdo->FixedSupply.VoltageIn50mV * 50,
				pdo->FixedSupply.MaxCurrentIn10mA * 10, pdo->FixedSupply.EPRModeCapable ? ", EPR capable" : "" );
		}
		else if ( USBPD_IsPPS( pdo ) )
		{
			LOG( "  %d: PPS %d-%d mV, %d mA", (int)i + 1, pdo->SPR_PPS.MinVoltageIn100mV * 100,
				pdo->SPR_PPS.MaxVoltageIn100mV * 100, pdo->SPR_PPS.MaxCurrentIn50mA * 50 );
		}
		else
		{
			LOG( "  %d: other (type %d/%d)", (int)i + 1, pdo->Header.PDOType, pdo->Header.AugmentedType );
		}
	}
}
#endif

#if PDCARD_LOG
static const char *const s_ctrlNames[] = {
	[0x01] = "GoodCRC", [0x02] = "GotoMin", [0x03] = "Accept", [0x04] = "Reject", [0x05] = "Ping",
	[0x06] = "PS_RDY", [0x07] = "Get_Source_Cap", [0x08] = "Get_Sink_Cap", [0x09] = "DR_Swap",
	[0x0A] = "PR_Swap", [0x0B] = "VCONN_Swap", [0x0C] = "Wait", [0x0D] = "Soft_Reset",
	[0x0E] = "Data_Reset", [0x0F] = "Data_Reset_Complete", [0x10] = "Not_Supported",
	[0x11] = "Get_Source_Cap_Extended", [0x12] = "Get_Status", [0x13] = "FR_Swap",
	[0x14] = "Get_PPS_Status", [0x15] = "Get_Country_Codes", [0x16] = "Get_Sink_Cap_Extended",
	[0x17] = "Get_Source_Info", [0x18] = "Get_Revision",
};
static const char *const s_dataNames[] = {
	[0x01] = "Source_Capabilities", [0x02] = "Request", [0x03] = "BIST", [0x04] = "Sink_Capabilities",
	[0x05] = "Battery_Status", [0x06] = "Alert", [0x07] = "Get_Country_Info", [0x08] = "Enter_USB",
	[0x09] = "EPR_Request", [0x0A] = "EPR_Mode", [0x0B] = "Source_Info", [0x0C] = "Revision",
	[0x0F] = "Vendor_Defined",
};
static uint32_t s_tracePrinted = 0;

// True when no PD event happened in the last 100 ms
static bool TraceQuiet( void )
{
	const uint32_t head = s_traceHead;
	if ( head == 0 ) return true;
	const uint32_t last = s_trace[( head - 1 ) % USBPD_TRACE_LEN].tick;
	return ( SysTick->CNTL - last ) >= FUNCONF_SYSTEM_CORE_CLOCK / 10;
}

static void LogTrace( void )
{
	const uint32_t head = s_traceHead;
	if ( !DidDebuggerAttach() ) return; // keep events until the terminal is open
	if ( head - s_tracePrinted > USBPD_TRACE_LEN )
	{
		LOG( "  (%d older events lost)", (int)( head - s_tracePrinted - USBPD_TRACE_LEN ) );
		s_tracePrinted = head - USBPD_TRACE_LEN;
	}

	for ( ; s_tracePrinted != head; s_tracePrinted++ )
	{
		const USBPD_TraceEntry_t *e = &s_trace[s_tracePrinted % USBPD_TRACE_LEN];
		const unsigned ms = e->tick / ( FUNCONF_SYSTEM_CORE_CLOCK / 1000 );
		if ( e->dir == '!' )
		{
			LOG( "%d ms !! Hard_Reset received", (int)ms );
			continue;
		}

		const USBPD_MessageHeader_t h = { .data = e->header };
		const char *name = NULL;
		if ( h.Extended ) name = "(extended)";
		else if ( h.NumberOfDataObjects == 0 && h.MessageType < sizeof( s_ctrlNames ) / sizeof( s_ctrlNames[0] ) )
			name = s_ctrlNames[h.MessageType];
		else if ( h.NumberOfDataObjects > 0 && h.MessageType < sizeof( s_dataNames ) / sizeof( s_dataNames[0] ) )
			name = s_dataNames[h.MessageType];

		// ch32fun's printf has no field widths or %x: plain %d / %s only
		LOG( "%d ms %s %s (type %d) id=%d n=%d rev=%d dr=%d pr=%d", (int)ms, e->dir == '<' ? "<-" : "->",
			name ? name : "?", h.MessageType, h.MessageID, h.NumberOfDataObjects, h.SpecificationRevision + 1,
			h.PortDataRole, h.PortPowerRole );
	}
}
#endif

// 1 ms tick. Same scheme as ch32fun's usbpd_sink example: the counter keeps
// running free, so Delay_Us()/Delay_Ms() still work.
static void SysTick_Init( void )
{
	SysTick->CTLR = 0;
	NVIC_EnableIRQ( SysTick_IRQn );

	uint64_t cnt = SysTick->CNTL | ( (uint64_t)SysTick->CNTH << 32 );
	cnt += ( FUNCONF_SYSTEM_CORE_CLOCK / 1000 ) - 1;
	SysTick->CMPL = (uint32_t)( cnt & 0xFFFFFFFF );
	SysTick->CMPH = (uint32_t)( cnt >> 32 );

	s_ms = 0;
	SysTick->CTLR = SYSTICK_CTLR_STE | SYSTICK_CTLR_STIE | SYSTICK_CTLR_STCLK;
}

void SysTick_Handler( void ) __attribute__( ( interrupt ) );
void SysTick_Handler( void )
{
	uint64_t cnt = SysTick->CNTL | ( (uint64_t)SysTick->CNTH << 32 );
	cnt += ( FUNCONF_SYSTEM_CORE_CLOCK / 1000 ) - 1;
	SysTick->CMPL = (uint32_t)( cnt & 0xFFFFFFFF );
	SysTick->CMPH = (uint32_t)( cnt >> 32 );
	SysTick->SR = 0;
	s_ms++;
}

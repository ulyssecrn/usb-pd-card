# PCB Business Card — Design Brief

Owner: Ulysse Corne (EE / embedded, looking for internships).
Goal: memorable, cheap PCB business cards for networking events.
Tool: KiCad (v7+). Fab + assembly: JLCPCB (PCBA). Prefer JLC "basic" parts; minimize extended parts (~$3 setup each).

Two designs:
- **Card A (v1, handout): battery-free NFC card with LED.** Priority.
- **Card B (v2, showpiece): USB-C PD tester card with PCB-paddle USB-C connector.**

---

## Shared requirements
- Outline: credit-card size 85.6 × 54 mm, rounded corners (r ≈ 3 mm).
- Look: matte black solder mask, white silkscreen, ENIG; exposed-copper (ENIG) art allowed.
- Silkscreen content: name, title ("Embedded / PCB / Firmware"), email `<EMAIL>`, LinkedIn `<LINKEDIN>`, site `<URL>`, QR code ≥ 20 mm (fallback for NFC), link to this card's open-source repo.
- Routing style: curved / arc traces are fine for aesthetics. Teardrops on. All parts on one side, low profile.
- Do not copy existing open-source cards; use them only as references for footprints and geometry.
- Target cost: ~$1.50–3 per card at qty 50, landed in the US.

---

## Card A — NFC + energy-harvesting LED (battery-free)
Behavior: when a phone taps the card, the phone opens `<URL>` and an LED on the card lights, powered by the NFC field.

Board: 0.8 mm FR4 (0.6 mm acceptable; more flexible, so keep parts away from the center). Target total thickness ≤ ~1.6 mm.

BOM:
- U1: NXP **NT3H2111** (NTAG I²C plus). Prefer XQFN8 (thin); TSSOP8 fallback. Check LCSC/JLC stock.
- Antenna: PCB spiral loop, 4–6 turns, ~40×30 mm or along the card edge. Target L ≈ 2.7 µH, resonating at 13.56 MHz with the chip's input capacitance; use the exact value from the datasheet. Base the geometry on an NXP reference antenna for this chip, and verify L with a calculator or field solver (e.g. ST eDesignSuite).
- C_tune: 0402 across LA/LB, DNP by default (tuning knob).
- VOUT cap: 100–220 nF. VCC tied to VOUT, plus 100 nF decoupling.
- LED: high-efficiency red or orange (low Vf). 0603, or a reverse-mount LED shining through a board hole for a flush look.
- R_LED: 100–470 Ω, target 1–2 mA.
- SDA/SCL: break out to test pads (unused in v1).

Layout rules:
- No copper pour inside or near the loop. Chip at the loop edge, short LA/LB traces.
- Keep the antenna region free of other traces and art copper.

Post-fab programming (per card, over NFC with NXP NTAG I²C tools/app or NFC Tools):
1. Enable energy harvesting and set the VOUT level in the config registers (off by default).
2. Write the NDEF URL record.
3. Lock the tag.

Validation: test read range and LED brightness with an iPhone and an Android. If dim, adjust C_tune.
Optional de-risk: 5-card prototype with 2–3 antenna variants before the full run.

---

## Card B — USB-C PD tester (no battery)
Behavior: plug any USB-C charger or cable into the card's edge. The card reads the charger's Source_Capabilities and lights LEDs for each advertised capability. It only ever requests 5 V (read-only, safe).

Board: **0.6 mm, ENIG required** (HASL can damage cable contacts).

Connector: PCB paddle acting as the USB-C receptacle tongue (the cable plug slides over the board edge). Reference geometry: github.com/Nicholas-L-Johnson/flip-card.
- Tongue width/length per the USB-C receptacle spec; side slots for the plug shell; chamfered leading edge.
- **Pads on both sides:** A-row top, B-row bottom, correctly mirrored, so it works in either orientation.
- **CC1 (A5) and CC2 (B5) both routed to the PD controller.** A single-sided paddle fails with C-to-C chargers in one orientation.
- VBUS and GND on both sides. D+/D− optional (not needed for v1).
- 0.5 mm pitch, ~0.25 mm pad width.

BOM:
- MCU with built-in USB PD PHY: **CH32X035** (preferred, cheap) or STM32G0 (UCPD).
- 3.3 V LDO from VBUS, input rated ≥ 24 V for margin.
- TVS on VBUS; ESD protection on CC1/CC2.
- LEDs + resistors, silkscreen-labeled: 5 V, 9 V, 12 V, 15 V, 20 V, PPS, EPR (28/36/48 V). Plus a 4–5 LED bar for max advertised wattage.
- Programming/debug pads (SWD/SWIO + GND + 3V3).

Firmware:
- PD sink: wait for Source_Capabilities, parse all PDOs (fixed, PPS, EPR), display them, request 5 V only.
- Deferred, not in v1: a "verify mode" that requests each voltage and measures it via an ADC divider. If added later, rate all input-side parts for 20 V (48 V if EPR).

Silkscreen: "Plug a USB-C cable here" next to the tongue.
Layout: short, wide VBUS/GND; follow the PD library's CC routing guidance.
Validation: test with several chargers (laptop brick, phone charger, cheap no-name), in both cable orientations.

---

## Deliverables expected from the agent
1. KiCad schematic + PCB for Card A, then Card B.
2. JLC-ready Gerbers, BOM, CPL; parts checked against JLC stock (flag extended parts).
3. For Card B: firmware project (PD sink + LED display) and a short README covering flashing and testing.
4. A list of open decisions or assumptions made, for review before ordering.

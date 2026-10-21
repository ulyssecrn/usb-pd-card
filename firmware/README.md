# usb-pd-card firmware

CH32X035 firmware for the card. Plug in a USB-C charger: the card reads the charger's
PD Source_Capabilities, lights the LEDs, and only ever asks for 5 V.

| LEDs | Meaning |
|---|---|
| 5V / 9V / 12V / 15V / 20V | The charger offers that fixed voltage |
| PPS | It offers a PPS (programmable) range |
| EPR | It can do EPR (28 V+); read from PDO #1, the card never enters EPR mode |
| 15W … 100W bar | Every step at or below the highest V × I offered |
| 5V blinking | No PD (plain Type-C source); 15W also lit if its Rp says 3 A |
| NFC | Hardware only (NT3H2111 harvesting); no firmware involved |

At power-up all 12 LEDs light one after another (~250 ms) as a self-test.

Built on [ch32fun](https://github.com/cnlohr/ch32fun) and its `usbpd_sink` example
library (`usbpd.h`), from the `mtabini/ch32fun` fork, which also has the RP2040 programmer.

## Setup

```sh
git submodule update --init      # firmware/ch32fun
cd firmware
nix-shell                        # RISC-V GCC + minichlink deps
make                             # -> pdcard.bin
```

## Programmer: YD-RP2040

The YD-RP2040 runs the fork's Pico programmer (`ch32fun_pico_programmer.uf2`, built from
`ch32fun/programmers/pico`; hold BOOT while plugging in, copy the `.uf2` to `RPI-RP2`).

| YD-RP2040 | Card test pad |
|---|---|
| GP2 | TP1 DIO (PC18) |
| GP3 | TP2 DCK (PC19) |
| GND | TP4 GND |
| 3V3 | TP3 3V3, **only if no USB-C charger is plugged into the card** |

Power the card one way only: the YD's 3V3, or a charger on the card's USB-C.

```sh
make detect                      # minichlink should report a CH32X035; do this first
make flash                       # PORT=/dev/ttyACM0 by default; the programmer is the first port
```

The programmer port is the one named "Ardulink Programmer" (`ttyACM0`). The other port,
"CH32 UART Bridge", is unused, since the card has no UART pads.

**Flashing tips.** The pads are 1 × 1 mm at 2.0 mm pitch (GND, DIO, DCK, 3V3), so dupont
pins held by hand work, but only barely. What `make detect` prints tells you what's wrong:
- `Got code ffffffff`: nothing answers (no contact, or no power).
- Random codes (`7fffffff`, `000007ff`, …): DIO and DCK are swapped, or a contact flickers.
- `Got code 00000000`: DIO is held low, usually because the DIO pin also touches the GND pad.

## Debug log

`make flash LOG=1` records every PD message sent or received (header fields, timestamp,
Hard Resets). It prints them over DIO/DCK once the CC line has been quiet for 100 ms,
together with the PDO list every 2 s. `make log` opens the terminal. Connecting reboots
the chip, so **start `make log` before plugging in the charger**, with GND/DIO/DCK
wired and the card powered by that charger.

**Capturing a reboot loop.** When the charger hard-resets, VBUS drops and the RAM log is
lost. To keep it:
1. Let the card loop on the charger, without 3V3 wired.
2. Touch the YD's 3V3 to the card's 3V3 pad during an "on" phase. When the charger cuts
   VBUS, the MCU stays alive on the YD.
3. The YD's 3.3 V then leaks back through U2 onto VBUS (~2.5–3 V). The charger only
   re-attaches from 0 V, so the loop stops with the LEDs steady. If you get the LED walk
   instead, you caught an "off" phase: lift the wire and retry.
4. `make logkeep` attaches without rebooting and prints the trace.

For the same reason, a card already powered from the YD's 3V3 never negotiates with a
newly plugged charger. Don't use the YD's 3V3 for normal PD testing.

## How it works

1. **Boot:** LED walk, then the USBPD peripheral is set for VDD = 3.3 V.
2. **CC detect:** the library watches CC1/CC2 for the charger's Rp, then listens on that line.
3. **Source_Capabilities:** the USBPD interrupt answers GoodCRC. The main loop waits 1 ms,
   then sends a Request for PDO #1 (5 V). The charger expects it within ~25 ms, so the loop
   never blocks.
4. **Accept, PS_RDY:** contract done; VBUS stays at 5 V.
5. **Display:** the LEDs are recomputed from the PDO list on every loop pass.
6. **No caps after 1.5 s:** treated as a plain Type-C source. The firmware reads the Rp level
   with the CC comparator (0.22 / 0.66 / 1.23 V thresholds) and blinks 5V.

## PD library

`usbpd.h` is a project copy of ch32fun's `examples_x035/usbpd_sink/usbpd.h`, with these changes:
- **CC2 attach:** the comparator gets 20 µs to settle after switching CC1/CC2 (was 1 µs). At
  1 µs it read the stale line, so a plug in the CC2 orientation never negotiated.
- **Data-role enum fixed:** the original had `UFP`/`DFP` swapped (spec: 0 = UFP). The original
  messages were correct only because the field was left at 0. Sending DFP made the Apple
  charger cut VBUS right after the LEDs lit (a reboot loop).
- **Transmit level:** each transmission enables the PHY's low-voltage output mode (`CC_LVE`):
  a 1.04–1.20 V swing (datasheet §3.3.10), the PD spec's vSwing. WCH's own driver does this.
  The original transmitted at VDD (3.3 V).
- **1 ms gap before the Request** (and before any reply) after our GoodCRC. The original sent
  it a few µs after the GoodCRC. A 33 W GaN charger never acknowledged it and hard-reset
  27 ms later, in a loop (found with the `LOG=1` trace).
- The card **answers** follow-up messages instead of only acknowledging them: Accept for
  Soft_Reset, a 5 V / 100 mA Sink_Capabilities for Get_Sink_Cap, and Not_Supported (PD 3.0)
  or Reject (PD 2.0) for anything else. Replies go out from the main loop once the GoodCRC
  transmission ends.

## CC diagnostic

`make flash CCDIAG=1` replaces PD with a live view of the CC comparators (5V blinks):

| LED | Meaning |
|---|---|
| 9V / 12V / 15V | CC1 (A5, PC14) above 0.22 / 0.66 / 1.23 V |
| 20V / PPS / EPR | CC2 (B5, PC15) above 0.22 / 0.66 / 1.23 V |

The active CC line lights two LEDs for a 1.5 A Rp, three for 3 A, and the other line none.
Flipping the plug should move the lights to the other group. This is how the CC2 attach bug
was found: both lines read correctly here, yet PD only worked on CC1.

## Tested sources (first card, 2026-10-21)

All of these behaved as designed, in both plug orientations where tried:

| Source | Card shows |
|---|---|
| Apple 35 W dual USB-C | 5/9/15/20 V, 30W |
| Apple MacBook 70 W | works |
| Anker GaN 70 W | 5/9/15/20 V, PPS, 65W |
| 33 W GaN (5/9/12/15/20 V, PPS) | as labeled, 30W (needed the 1 ms Request gap) |
| Cheap phone charger (5/9/12 V) | 5/9/12 V, PPS (a PPS PDO the label doesn't mention) |
| Lenovo ThinkPad brick | works |
| Power bank, 18 W | 5/9/12 V, 15W |
| Laptop USB-C port | 5V + 15W (PD, 5 V 3 A only) |
| Generic "3 A" USB-C chargers | blinking 5V + 15W (no PD, 3 A Rp) |
| iPhone as a source | blinking 5V (no PD) |

## Known limits (v1)

- **The replies are untested on hardware.** No tested charger is known to have sent a
  post-contract message (Get_Sink_Cap, Soft_Reset, a VDM), so that path hasn't run yet.
- **No retransmission.** If one of our messages isn't acknowledged, the library doesn't
  retry as the spec asks. The charger hard-resets, the card reboots, and the next attempt
  usually works (an extra LED walk).
- **PD 2.0-only chargers** (roughly 2016–2018) are untested.
- The library detects attach at 0.66 V on CC, so a PD charger advertising default-USB Rp
  (~0.41 V) is shown as "no PD".
- The Request uses the library default (PDO #1 at its full max current). The card draws
  ~20 mA, so this is harmless.

## Pins

LED map and pin rules are in `../AGENTS.md`. Never configure PB5 (it shares pin 16 with
PB1, the EPR LED), PB7 or PC16. The internal CC pull-down (`CC_PD`) stays off because the
board has external 5.1 kΩ Rd.

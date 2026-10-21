# usb-pd-card

A credit-card-sized PCB business card that is also a **USB-C PD charger tester** and a **battery-free NFC tag**.

![The v1 cards: back with contact info and QR code, front with the PD tester LEDs and NFC coil](docs/images/card-photo.jpg)

![Plugging in a charger: LED self-test, then 5/9/15/20 V and the 30 W bar](docs/images/card-plug-in.gif)

## What it does
- **USB-C PD tester:** plug any USB-C charger or cable into the card edge.
  - The CH32X035 MCU reads the charger's advertised capabilities and lights one LED each for 5 V / 9 V / 12 V / 15 V / 20 V / PPS / EPR.
  - A 5-LED bar shows max power: 15, 30, 45, 65, 100 W.
  - It only ever asks the charger for 5 V.
  - A charger without PD blinks the 5V LED (and lights 15W if it advertises 3 A on CC).
- **NFC:** tap a phone on the coil and it opens [ulysse.corne.sh](https://ulysse.corne.sh). No battery: the NT3H2111 tag and its LED run on energy harvested from the phone's field.

## Hardware
| | |
|---|---|
| Board | 85.6 × 54 mm (ID-1), 0.6 mm FR4, 2 layers, ENIG, matte black mask |
| USB-C | PCB-edge paddle, tongue cut into the board; CC1/CC2 with 5.1 kΩ Rd + ESD |
| MCU | WCH CH32X035G8U6 (RISC-V, built-in USB PD PHY) |
| Power | ME6228 3.3 V LDO from VBUS, SMF20A TVS |
| NFC | NXP NT3H2111 + on-board 5-turn coil (≈ 2.3 µH estimated) |
| Assembly | JLCPCB PCBA, all parts on the front |

## Repo layout
- `usb-pd-card.kicad_*`: KiCad 10 project (schematic + PCB)
- `lib/`: project symbols and footprints (USB-C paddle derived from [flip-card](https://github.com/Nicholas-L-Johnson/flip-card), MIT)
- `lib/nfc-coils.pretty/`: generated NFC coil footprints
- `tools/nfc_coil.py`: coil generator and inductance estimator (plain Python, no dependencies). Try `python3 tools/nfc_coil.py selftest`.
- `firmware/`: CH32X035 firmware (ch32fun, `nix-shell`, flashed with an RP2040 programmer). See [`firmware/README.md`](firmware/README.md).
- `jlcpcb/`: v1 production files (Gerbers, BOM, CPL)
- `AGENTS.md`: full design notes, pin map and decisions

## Status
- **v1 works.** 30 boards built by JLCPCB, received in October 2026.
- **USB-C PD:** the firmware reads every charger tried correctly, in both plug orientations (Apple, Anker, Lenovo, GaN chargers, power banks, plain 5 V chargers).
- **NFC:** a phone tap opens the site, and the NFC LED lights from the phone's field. The NT3H2111 ships unformatted and must be formatted once per card (see `AGENTS.md`).
- **Still to do:** measure the coil's resonance and choose the tuning capacitor (C3), test NFC read range, and flash and program the remaining cards.

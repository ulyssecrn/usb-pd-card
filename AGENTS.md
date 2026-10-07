# PCB Business Card — Design Brief

Owner: Ulysse Corne (EE / embedded, looking for internships).
Goal: memorable, cheap PCB business cards for networking events.
Tool: KiCad 10. Fab + assembly: JLCPCB (PCBA). Prefer JLC "basic"/"preferred" parts; minimize extended parts (~$3 setup each).

**Current build: one card, `usb-pd-card` (KiCad project at the repo root).** It is the USB-C PD tester with the battery-free NFC tag merged onto the same board. A standalone NFC-only handout card (old "Card A") is deferred.

## How the agent works on this repo
- **The owner draws the schematic and PCB by hand.** The agent gives guidance (part choice, datasheet facts, pin maps, layout advice), checks the owner's work (ERC/DRC, netlist review, renders), and imports or cleans footprints and symbols into `lib/`.
- Edit `usb-pd-card.kicad_sch` or `.kicad_pcb` only when explicitly asked, and only while the file is closed in KiCad (no `~<file>.lck` next to it). Verify edits by exporting the netlist before and after.
- Project libraries: `lib/business-card.kicad_sym` and `lib/business-card.pretty/` (registered in the repo-root `sym-lib-table` / `fp-lib-table`). Import JLC parts with `easyeda2kicad --full --lcsc_id <C…> --output "$PWD/lib/business-card" --project-relative` (the output path must be absolute), then `kicad-cli sym upgrade` / `fp upgrade`.
- Every BOM part carries an `LCSC` field. Board-only items (paddle J1, coil L1, test pads) are excluded from the BOM.
- Datasheets are kept locally in `docs/datasheets/` (git-ignored; links below).

---

## Shared requirements
- Outline: credit-card size 85.6 × 54 mm, rounded corners (r ≈ 3 mm).
- Board: **0.6 mm FR4, ENIG required** (HASL can damage cable contacts). Matte black solder mask, white silkscreen; exposed-copper (ENIG) art allowed away from the antenna.
- Silkscreen content: name, title ("Embedded / PCB / Firmware"), email `<EMAIL>`, LinkedIn `<LINKEDIN>`, site `<URL>`, QR code ≥ 20 mm (fallback for NFC), link to this card's open-source repo, "Plug a USB-C cable here" next to the tongue, labels for every LED.
- Routing style: curved / arc traces are fine for aesthetics. Teardrops on. All parts on one side, low profile.
- Do not copy existing open-source cards; use them only as references for footprints and geometry.
- Target cost: ~$1.50–3 per card at qty 50, landed in the US.

## Behavior
- **USB-C:** plug any USB-C charger or cable into the card edge. The MCU reads the charger's Source_Capabilities, lights one LED per advertised capability (5 V, 9 V, 12 V, 15 V, 20 V, PPS, EPR) plus a 5-LED bar for max wattage, and only ever requests 5 V.
- **NFC (no USB needed):** a phone tap opens `<URL>` and the NFC LED lights from harvested field energy.

## References
- `../flip-card` (MIT, github.com/Nicholas-L-Johnson/flip-card): PCB-edge USB-C paddle. Imported as `business-card:USB_C_Paddle` (paste removed from contacts, excluded from BOM/CPL).
- `../koda-business-card`: NFC card with NT3H2111. Hex spiral coil, 7 turns, 0.3 mm track / 0.3 mm gap, ~32.8 mm across flats outside, ~25.6 mm inside, on B.Cu with an F.Cu bridge; schematic value 2.78 µH. Its tuning cap value (440 nF) is wrong — tuning caps are a few pF.
- Datasheets: [NT3H2111](https://www.nxp.com/docs/en/data-sheet/NT3H2111_2211.pdf) · [CH32X035](https://wmsc.lcsc.com/wmsc/upload/file/pdf/v2/lcsc/2404070952_WCH-Jiangsu-Qin-Heng-CH32X035G8U6_C7437027.pdf) · [HT75xx-1](https://www.farnell.com/datasheets/2047678.pdf)

---

## USB-C paddle
- Paddle acts as the receptacle tongue: 6.5 mm wide, tip flush with the card edge, **0.92 mm-wide × 4.46 mm-deep slots** each side (out to ±4.17 mm) for the plug shell, +0.2 mm clearance at the base. Rotate the footprint 180° so the tip faces the edge.
- A row on F.Cu, B row on B.Cu, mirrored. **CC1 (A5) and CC2 (B5) both go to the MCU.** VBUS and GND on both sides.
- **D+/D− left unconnected** (PC17 is the MCU BOOT pin, and chargers can drive D+ to ~2.7 V).

## Schematic (as built)
| Block | Parts / connections |
|---|---|
| VBUS input | D1 SMF20A TVS (cathode on VBUS), C2 10 µF 25 V. Total VBUS capacitance ≤ 10 µF (USB limit). |
| 3.3 V | U2 HT7533-1 (30 V in, 100 mA), C4 10 µF out (datasheet: 10 µF in / 10 µF out). |
| MCU | U1 CH32X035G8U6 (QFN-28). VDD on +3V3 with C5 100 nF. |
| CC lines | CC1 → PC14 (pin 28), CC2 → PC15 (pin 1). Each: 5.1 kΩ Rd to GND + H7VL10B ESD to GND. Nothing else on CC. |
| VBUS sense | 100 kΩ / 15 kΩ divider → PC3 (ADC A13). |
| BOOT | PC17 (pin 27) 10 kΩ to GND, otherwise unused. |
| Debug | TP1 SWIO = PC18, TP2 SWCLK = PC19, TP3 +3V3, TP4 GND (WCH-LinkE). |
| LEDs | 12 × red 0603 via 1 kΩ (~1.4 mA), GPIO → R → LED → GND on PA0–PA7, PB0, PB1, PB3, PB4. |
| NFC | U3 NT3H2111 standalone: L1 coil 2.75 µH across LA/LB, C3 tuning cap DNP, VCC tied to VOUT, C1 220 nF, R1 47 Ω → red LED. SCL/SDA/FD not connected; VSS on GND. |

## Datasheet facts that drive the design
- **CH32X035:** no built-in Rd without the CH211 companion chip, so external 5.1 kΩ Rd is required for dead-battery attach. PD works for VDD 3.0–5.3 V. I/O max is VDD + 0.3 V. PC17 high at power-up enters the bootloader. Hardware I²C and ADC channels 3/7/11/15 are missing on some lots (5th-from-last lot digit = 0), so bit-bang I²C if ever needed. PB1 and PB5 share pin 16 — never drive PB5. Keep the internal CC pull-down disabled in firmware (external Rd is fitted).
- **NT3H2111:** Ci = 50 pF (44–56) → L ≈ 2.75 µH at 13.56 MHz. Energy harvesting is always on (no enable/VOUT-level registers). VOUT ≈ 2 V at ~5 mA from a phone, 3.3 V max; VOUT capacitance 150–220 nF total. I²C address 0x55. Center pad of XQFN8 is not soldered — no traces/vias under it.
- **HT7533-1:** application circuit uses 10 µF in and out; no ESR requirement stated; ceramic is fine.

## BOM (all in stock at JLC, Oct 2026)
| Refs | Part | LCSC | JLC type |
|---|---|---|---|
| U1 | CH32X035G8U6 | C7437027 | extended |
| U3 | NT3H2111W0FHKH | C710403 | extended |
| U2 | HT7533-1 | C14289 | basic |
| D1 | SMF20A | C41411782 | preferred |
| D3, D4 | H7VL10B | C20615787 | preferred |
| D2, D5–D16 | KT-0603R red | C2286 | basic |
| C1 | 220 nF 0402 | C16772 | basic |
| C2 | 10 µF 25 V 0805 | C15850 | basic |
| C4 | 10 µF 10 V 0603 | C19702 | basic |
| C5 | 100 nF 0402 | C1525 | basic |
| R1 | 47 Ω 0402 | C25118 | preferred |
| R2, R3 | 5.1 kΩ 0402 | C25905 | basic |
| R4 / R5 / R6 | 100 k / 15 k / 10 k 0402 | C25741 / C25756 / C25744 | basic |
| R7–R18 | 1 kΩ 0402 | C11702 | basic |

## Layout rules
- Coil on one half of the card, electronics + paddle on the other (Koda-style split). No copper pour, traces or art copper inside or near the coil; keep the paddle, plug shell and VBUS/GND copper ≥ ~5 mm away. NT3H2111 at the coil edge with short LA/LB.
- ESD/TVS parts right at the paddle pads, then Rd, then the MCU. Short, wide VBUS/GND.
- Silkscreen over the coil is fine.

## Firmware
- PD sink: wait for Source_Capabilities, parse all PDOs (fixed, PPS, EPR), display them, request 5 V only.
- Deferred, not in v1: "verify mode" that requests each voltage and measures it via the VBUS divider. If added, rate all input-side parts for 20 V (48 V if EPR).

## NFC programming (per card, NXP NTAG I²C app or NFC Tools)
1. Write the NDEF URL record.
2. Protect it: prefer password protection (AUTH0/PWD) over a permanent lock so the URL can be changed later.

## Validation
- NFC: read range and LED brightness with an iPhone and an Android; if weak, fit C_tune (a few pF). Optional 5-card prototype with 2–3 coil variants.
- USB-C: several chargers (laptop brick, phone charger, cheap no-name), both cable orientations.

## Remaining deliverables
1. PCB layout (owner), then JLC Gerbers, BOM, CPL.
2. Firmware project (PD sink + LED display) with a short README on flashing (WCH-LinkE) and testing.
3. Open decisions to settle before ordering: final `<EMAIL>`/`<LINKEDIN>`/`<URL>`, coil geometry and measured L, LED labels/layout.

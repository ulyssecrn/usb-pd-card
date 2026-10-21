# PCB Business Card — Design Brief

Owner: Ulysse Corne (EE / embedded, looking for internships).
Goal: memorable, cheap PCB business cards for networking events.
Tool: KiCad 10. Fab + assembly: JLCPCB (PCBA). Prefer JLC "basic"/"preferred" parts; minimize extended parts (~$3 setup each).

**Current build: one card, `usb-pd-card` (KiCad project at the repo root).** It is the USB-C PD tester with the battery-free NFC tag merged onto the same board. A standalone NFC-only handout card (old "Card A") is deferred.

**Status: v1 ordered from JLCPCB on 2026-10-11** (tag `v1`; files in `jlcpcb/`), received 2026-10-21. First card brought up: PD and NFC work.
- Order: 30 boards; 2 layers, 0.6 mm, black mask, ENIG, outline tolerance ±0.2 mm, JLC mark removed. Confirm Production File and Confirm Parts Placement are both on.
- Price: PCB $42.70 + Standard PCBA $127.94, before shipping and duties.
- JLC adds 9 mm edge rails along the long edges (panel 85.6 × 71.98 mm), and the boards arrive with the rails attached. Snap them off and sand the tab nubs.
- Firmware: `firmware/` (ch32fun + a project copy of its `usbpd.h`; `nix-shell` toolchain). Works on all 10 sources tried, in both plug orientations (list in `firmware/README.md`).

## How the agent works on this repo
- **The owner draws the schematic and PCB by hand.** The agent gives guidance (part choice, datasheet facts, pin maps, layout advice), checks the owner's work (ERC/DRC, netlist review, renders), and imports or cleans footprints and symbols into `lib/`.
- Edit `usb-pd-card.kicad_sch` or `.kicad_pcb` only when explicitly asked, and only while the file is closed in KiCad (no `~<file>.lck` next to it). Verify edits by exporting the netlist before and after.
- Project libraries: `lib/business-card.kicad_sym` and `lib/business-card.pretty/` (registered in the repo-root `sym-lib-table` / `fp-lib-table`). Import JLC parts with `easyeda2kicad --full --lcsc_id <C…> --output "$PWD/lib/business-card" --project-relative` (the output path must be absolute), then `kicad-cli sym upgrade` / `fp upgrade`.
- Every BOM part carries an `LCSC` field. Board-only items (paddle J1, coil L1, test pads) are excluded from the BOM and position files; C3 is DNP.
- Production files come from Bouni's **kicad-jlcpcb-tools** plugin (KiCad PCM, repo `https://raw.githubusercontent.com/Bouni/bouni-kicad-repository/main/repository.json`) into `jlcpcb/`. The plugin keeps its own LCSC assignments in `jlcpcb/project.db`; after changing a part, check that `jlcpcb/production_files/BOM-*.csv` matches the footprint `LCSC` fields (v1 once exported a stale C2).
- Datasheets are kept locally in `docs/datasheets/` (git-ignored; links below).

---

## Shared requirements
- Outline: credit-card size (ISO 7810 ID-1) 85.6 × 54 mm, corner radius 3.18 mm, so it fits a wallet card slot. Keep every part ≤ ~1.1 mm tall (SOT-23, 0603, SOD-123FL) so the card stays ~1.7 mm thick.
- Board: **0.6 mm FR4, 2 layers, 1 oz, ENIG required** (HASL can damage cable contacts). **Matte black solder mask, white silkscreen.** Gold (exposed-ENIG) art is allowed ≥ 5 mm from the coil, never as a closed loop near it. The coil stays under mask: exposing it would put the NT3H2111 LA/LB pins (rated only 2 kV HBM) directly under fingers.
- Silkscreen (v1 as built):
  - **Back (business-card side):** "Ulysse Corne", "electronics • embedded systems", `ulysse.corne.sh`, `ucorne@andrew.cmu.edu`, `github.com/ulyssecrn`, `linkedin.com/in/ulysse-corne`, an NFC icon, and a 20 mm QR code for `https://ulysse.corne.sh` (B.SilkS barcode, knockout on, ECC M).
  - **Front (component side):** "USB-C PD CHARGER TESTER", every LED label, test-pad labels (GND / DIO / DCK / 3V3), `github.com/ulyssecrn/usb-pd-card · v1 · 2026`, and an NFC icon + "NFC" inside the coil.
  - Not on v1: a "plug USB-C here" label by the tongue.
- Routing style: curved / arc traces are fine for aesthetics. Teardrops on. All parts on one side, low profile.
- Do not copy existing open-source cards; use them only as references for footprints and geometry. **Known exception in v1:** both NFC icons are Koda's footprints (`koda:nfctap` on the front, `koda:tapsmall` on the back; the `koda` library is not in the project table, so DRC warns). Replace them with original artwork in v2.
- Target cost was ~$1.50–3 per card. Actual JLC quotes: 5 boards ≈ $112 before shipping; 30 boards ≈ $280 including shipping and duties (≈ $9.30/card). The fixed fees dominate: the 0.6 mm board forces Standard PCBA (setup ≈ $26 + thin-board fixture ≈ $17), plus per-part-type feeder fees for extended/preferred parts (≈ $25) and ENIG (≈ $17).

## Behavior
- **USB-C:** plug any USB-C charger or cable into the card edge. The MCU reads the charger's Source_Capabilities, lights one LED per advertised capability (5 V, 9 V, 12 V, 15 V, 20 V, PPS, EPR) plus a 5-LED bar for max wattage, and only ever requests 5 V.
- **NFC (no USB needed):** a phone tap opens `https://ulysse.corne.sh` (root path, so it never breaks) and the NFC LED lights from harvested field energy.

## References
- `../flip-card` (MIT, github.com/Nicholas-L-Johnson/flip-card): PCB-edge USB-C paddle. Imported as `business-card:USB_C_Paddle` (paste removed from contacts, excluded from BOM/CPL).
- `../koda-business-card`: NFC card with NT3H2111. Hex spiral coil, 7 turns, 0.3 mm track / 0.3 mm gap, ~32.8 mm across flats outside, ~25.6 mm inside, on B.Cu with an F.Cu bridge; schematic value 2.78 µH. Its tuning cap value (440 nF) is wrong — tuning caps are a few pF.
- Datasheets: [NT3H2111](https://www.nxp.com/docs/en/data-sheet/NT3H2111_2211.pdf) · [CH32X035](https://wmsc.lcsc.com/wmsc/upload/file/pdf/v2/lcsc/2404070952_WCH-Jiangsu-Qin-Heng-CH32X035G8U6_C7437027.pdf) · [ME6228](https://wmsc.lcsc.com/wmsc/upload/file/pdf/v2/lcsc/2304140030_MICRONE-Nanjing-Micro-One-Elec-ME6228A33M3G_C487914.pdf)

---

## USB-C paddle
- Paddle acts as the receptacle tongue: 6.5 mm wide, tip flush with the card edge, **0.92 mm-wide × 4.46 mm-deep slots** each side (out to ±4.17 mm) for the plug shell, +0.2 mm clearance at the base. Rotate the footprint so the tip is flush with the edge (v1: left edge, J1 at 90°). The footprint's 24 pads and 13 Edge.Cuts segments are identical to flip-card's, which was built on a 0.6 mm board.
- A row on F.Cu, B row on B.Cu, mirrored. **CC1 (A5) and CC2 (B5) both go to the MCU.** VBUS and GND on both sides.
- **D+/D− left unconnected** (PC17 is the MCU BOOT pin, and chargers can drive D+ to ~2.7 V).

## Schematic (as built)
| Block | Parts / connections |
|---|---|
| VBUS input | D1 SMF20A TVS in SOD-123FL (cathode on VBUS), C2 10 µF 25 V 0603. Total VBUS capacitance ≤ 10 µF (USB limit). |
| 3.3 V | U2 ME6228A33M3G, SOT-23-3 (pin 1 VSS, 2 VOUT, 3 VIN; 30 V in, 150 mA), C2 in / C4 10 µF out. |
| MCU | U1 CH32X035G8U6 (QFN-28). VDD on +3V3 with C5 100 nF. |
| CC lines | CC1 → PC14 (pin 28), CC2 → PC15 (pin 1). Each: 5.1 kΩ Rd to GND + H7VL10B ESD to GND. Nothing else on CC. |
| VBUS sense | 100 kΩ / 15 kΩ divider → PC3 (ADC A13). |
| BOOT | PC17 (pin 27) 10 kΩ to GND, otherwise unused. |
| Debug | TP1 SWIO = PC18, TP2 SWCLK = PC19, TP3 +3V3, TP4 GND (programmed with the owner's YD-RP2040 running the `mtabini/ch32fun` Pico programmer: GP2 = DIO, GP3 = DCK; no WCH-LinkE). |
| LEDs | 12 × red 0603 via 1 kΩ (~1.4 mA), GPIO → R → LED → GND. Pin map below. |
| NFC | U3 NT3H2111 standalone: L1 coil 2.75 µH across LA/LB, C3 tuning cap DNP, VCC tied to VOUT, C1 220 nF, R1 47 Ω → red LED. SCL/SDA/FD not connected; VSS on GND. |

### LED pin map (firmware)
| Label | LED | GPIO | | Label | LED | GPIO |
|---|---|---|---|---|---|---|
| 5V | D10 | PA5 | | 100W | D5 | PA0 |
| 9V | D11 | PA6 | | 65W | D6 | PA1 |
| 12V | D12 | PA7 | | 45W | D7 | PA2 |
| 15V | D13 | PB0 | | 30W | D8 | PA3 |
| 20V | D15 | PB3 | | 15W | D9 | PA4 |
| PPS | D16 | PB4 | | NFC | D2 | (NT3H VOUT via R1, not MCU) |
| EPR | D14 | PB1 | | | | |

- **5V LED:** steady when the source speaks PD; blinks for a plain Type-C source (read its Rp current level from CC).
- **Wattage bar:** lights up to the highest threshold ≤ the max offered power (V × I over all PDOs).
- **Spare GPIOs:** PB6, PB8–PB12, PC0. Avoid PB7 (can be the reset pin) and PC16 (bonded with PC11).

## Datasheet facts that drive the design
- **CH32X035:** no built-in Rd without the CH211 companion chip, so external 5.1 kΩ Rd is required for dead-battery attach. PD works for VDD 3.0–5.3 V. I/O max is VDD + 0.3 V. PC17 high at power-up enters the bootloader. Hardware I²C and ADC channels 3/7/11/15 are missing on some lots (5th-from-last lot digit = 0), so bit-bang I²C if ever needed. PB1 and PB5 share pin 16 — never drive PB5. Keep the internal CC pull-down disabled in firmware (external Rd is fitted).
- **NT3H2111:** Ci = 50 pF (44–56) → L ≈ 2.75 µH at 13.56 MHz. Energy harvesting is always on (no enable/VOUT-level registers). VOUT ≈ 2 V at ~5 mA from a phone, 3.3 V max; VOUT capacitance 150–220 nF total. I²C address 0x55. Center pad of XQFN8 is not soldered — no traces/vias under it.
- **ME6228A33M3G:** characterised with 10 µF ceramic in and out (X5R/X7R, low ESR is stable). Dropout ≈ 0.12 V @ 10 mA, 0.55 V @ 50 mA; Iq 0.7 µA. Above 15 V input the datasheet requires an electrolytic/tantalum input cap (ceramic hot-plug spikes can exceed 40 V) — matters only for the deferred 20 V verify mode.

## BOM (all in stock at JLC, Oct 2026)
| Refs | Part | LCSC | JLC type |
|---|---|---|---|
| U1 | CH32X035G8U6 | C7437027 | extended |
| U3 | NT3H2111W0FHKH | C710403 | extended |
| U2 | ME6228A33M3G (SOT-23-3) | C487914 | extended |
| D1 | SMF20A (SOD-123FL) | C41411782 | preferred |
| D3, D4 | H7VL10B | C20615787 | preferred |
| D2, D5–D16 | KT-0603R red | C2286 | basic |
| C1 | 220 nF 0402 | C16772 | basic |
| C2 | 10 µF 25 V 0603 | C96446 | basic |
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
- **v1 as built:**
  - Paddle on the left edge; electronics, LEDs and test pads on the left ~40 %.
  - GND pour on both layers over that half only, plus one GND trace along the top edge to U3.
  - Coil on the right half: `nfc-coils:NFC_Coil_Rect_38x46mm_R4_5T_W0.5_S0.3`, rotated −90° (46 × 38 mm on the board, r4, 5 turns, 0.5 mm track / 0.3 mm gap), ≈ 5 mm from the card edges and the pour.
  - U3 / C1 / C3 / R1 / D2 above the coil, with C3 across LA/LB at U3. The inner via goes out through a straight B.Cu bridge.
  - **Estimated L as routed = 2.31 µH (X_L ≈ 197 Ω at 13.56 MHz), f0 ≈ 14.4 MHz untuned with 50 + 3 pF; ≈ 6.6 pF in C3 would pull it to 13.56 MHz. C3 is DNP on v1; pick it (C0G) from prototype tests. Measured L: TBD.**
- Known accepted DRC items in v1:
  - The barcode clearance error: U1's center-pad GND via lands in a dark QR module.
  - The `koda` library warnings.
  - The J1 `SH` pin with no pad.
- No vias in SMD pads, except the single GND via in U1's center pad. Test pads may have vias.
- Coil footprints come from `tools/nfc_coil.py` (standalone Python, no KiCad needed): it estimates L / f0 / C3 for each geometry and `--write`s net-tie footprints into `lib/nfc-coils.pretty` (pad 1 = outer end → LA, pad 2 = inner via → B.Cu bridge along y = 0 → LB; built-in no-pour rule area). Target f0 ≈ 14–14.5 MHz untuned with 50 + 3 pF, because C3 can only lower it. `selftest` checks the solver against textbook loops and the Koda coil.

## Firmware
- PD sink: wait for Source_Capabilities, parse all PDOs (fixed, PPS, EPR), display them, request 5 V only. Build, flash, debug log and LED meanings are in `firmware/README.md`.
- Toolchain: `firmware/shell.nix` uses the prebuilt nixpkgs `riscv32-none-elf` GCC. Its libgcc is hard-float (rv32gc / ilp32d), which is fine while nothing pulls from libgcc. If the link ever fails on float ABI, switch to an rv32imac / ilp32 cross toolchain.
- `usbpd.h` (from ch32fun's `usbpd_sink` example) needed five fixes before it worked on every charger: CC2 attach (20 µs comparator settle), a swapped UFP/DFP enum, CC_LVE transmit level, a 1 ms gap before the Request, and replies to post-contract messages. Details are in `firmware/README.md`.
- Debug link gotchas:
  - `minichlink -T` reboots the chip on connect, and `-k` only works combined (`-kT`).
  - The YD's 3V3 on TP3 back-feeds VBUS through U2 (~2.5–3 V), so a charger won't attach while the YD powers the card. The README uses this on purpose to capture reboot loops.
- Deferred, not in v1: "verify mode" that requests each voltage and measures it via the VBUS divider. If added, rate all input-side parts for 20 V (48 V if EPR).

## NFC programming (per card, NXP NTAG I²C app or NFC Tools)
0. Format it. The NT3H2111 ships with CC = 00 00 00 00 (datasheet §8.3.10), so iOS reports "not NDEF compliant". NFC Tools → Other → Advanced NFC commands: `A2 04 03 00 FE 00`, then `A2 03 E1 10 6D 00`. Check page 03 in NXP TagInfo. CC bits can only go 0 → 1 over NFC, and I²C isn't wired, so a wrong byte is permanent. Verified on the first card, 2026-10-21.
1. Write the NDEF URL record.
2. Protect it: prefer password protection (AUTH0/PWD) over a permanent lock so the URL can be changed later.

## Validation
- NFC: read range and LED brightness with an iPhone and an Android. If weak, fit C3 (C0G, ~4.7–6.8 pF). With a NanoVNA, look for the S11 dip from a pickup loop and aim for 13.56–14.5 MHz.
- QR: scan the back with iPhone and Android cameras.
- USB-C: done on the first card (10 sources, both orientations; see `firmware/README.md`). Still untested: PD 2.0-only bricks, and any charger that sends post-contract messages.

## Ordering checklist (JLC)
1. Upload `jlcpcb/production_files/GERBER-usb-pd-card.zip`. Options: 2 layers, 0.6 mm, ENIG, black mask, white silkscreen, order-number placement/removal, PCBA top side only (Standard).
2. Upload `BOM-usb-pd-card.csv` (16 lines, 41 parts) and `CPL-usb-pd-card.csv` (41 parts).
3. **In JLC's placement preview, check rotations:** U1 pin-1 dot, D1 cathode band toward VBUS, all 13 LEDs with the cathode toward GND, U2 and U3 pin 1. Stock KiCad footprints (QFN, SOD-123F, LED_0603) are the usual offenders.

## Remaining deliverables
1. ~~Order v1~~ (done 2026-10-11). At JLC's confirmations: check that no tabs land near the USB-C tongue, and check placement rotations (checklist above).
2. ~~Firmware project~~ (`firmware/`, working on hardware 2026-10-21).
3. Bring-up: ~~paddle fit in real plugs (both orientations)~~, ~~PD on several chargers~~, ~~NFC read/write from an iPhone~~ (after the format step); still to do: NFC range, choice of C3, measured coil resonance.
4. The other 29 cards: flash (`make flash`), format and write the NFC tag (steps above), and a quick charger check.
5. v2 ideas:
   - original NFC icons;
   - a "plug USB-C here" label;
   - gold accent art;
   - set the stackup copper finish to ENIG (currently "None"; this only affects the 3D view).
   - maybe switch the USB-C paddle from ENIG to hard-gold "gold fingers" (plus a bevelled edge): the ENIG on the first v1 card was already wearing through after a day of plug cycles (2026-10-21). Check that JLC offers it on 0.6 mm boards, and its cost.

# Cirrus PCBs

The Cirrus left board: the original Caldera left board plus a side-emitting status LED
(SK6812SIDE-A-RVS) on the inner edge next to the controller's USB port, with a small transistor
switch so the firmware can cut the LED's power during sleep. The printed board text reads "Cirrus".

- `cirrus_left.kicad_pcb` / `.kicad_pro`: the Cirrus left board (open in KiCad 10)
- `cirrus.pretty/`: custom footprints (the LED)
- `base/left_v1_kicad10.kicad_pcb`: the original Caldera left board, upgraded to KiCad 10 format (starting point)
- `scripts/add_led_circuit.py`: rebuilds the Cirrus board from the base: renames the board text,
  places the parts and routes them. Run with KiCad's Python, from this folder:
  `"C:\Program Files\KiCad\10.0\bin\python.exe" scripts\add_led_circuit.py base\left_v1_kicad10.kicad_pcb cirrus_left.kicad_pcb cirrus.pretty`
- `scripts/router.py`: small maze router used by the script

## Right board
`cirrus_right.kicad_pcb` is the original Caldera right board (`../ergogen/output/pcbs/right_finished.kicad_pcb`)
with only the printed name changed to "Cirrus". No LED (the light lives on the left half).
`base/right_v1_kicad10.kicad_pcb` is the untouched original in KiCad 10 format. Rebuild with:
`"C:\Program Files\KiCad\10.0\bin\python.exe" scripts\make_right_board.py ..\ergogen\output\pcbs\right_finished.kicad_pcb`

## New parts on the left board (all on the back, all assembled by JLCPCB)
| Ref | Part | JLCPCB # | Job |
|---|---|---|---|
| LED1 | SK6812SIDE-A-RVS | C2890037 | status LED, data from P0.06 |
| Q1 | DMG1013UW (P-MOSFET, SOT-323) | C3040603 | switches battery (RAW) to the LED |
| Q2 | 2N7002WT1G (N-MOSFET, SOT-323) | C232391 | lets P0.08 drive Q1 |
| R1 | 100k 0402 | C25741 | keeps Q1 off by default |
| R2 | 100k 0402 | C25741 | keeps Q2 off while the controller boots |
| C1 | 100nF 0402 | C1525 | LED power smoothing |

Firmware: P0.08 HIGH = LED powered; LED data on P0.06 (Pro Micro pin 1).

## Ordering from JLCPCB
Files are in `jlcpcb/` (regenerate with `scripts\make_jlcpcb_files.py left` or `... right`):
- Left: `cirrus_left_gerbers.zip`, `cirrus_left_bom.csv`, `cirrus_left_cpl.csv` (38 parts; ordered 2026-11-10)
- Right: `cirrus_right_gerbers.zip`, `cirrus_right_bom.csv`, `cirrus_right_cpl.csv` (32 parts: 30 diodes,
  reset button, power switch)

1. Upload the side's `_gerbers.zip`. Keep: 2 layers, 1.6 mm thick, lead-free finish (HASL lead-free or ENIG).
2. Turn on **PCB Assembly**: choose **Standard** PCBA (the LED is a "Standard only" part),
   **Bottom** side, and the quantity to assemble (2 is enough for one keyboard plus a spare).
   If JLCPCB asks about edge rails / process edges, accept: the LED sits right at the board edge.
   Use the same settings for the right board (it has no LED, but Standard is the known-good path).
3. Upload the side's `_bom.csv` and `_cpl.csv`.
4. **Check the placement preview carefully** before paying. Part rotation conventions differ
   between KiCad and JLCPCB, so fix any part that looks turned in their viewer:
   - LED1 (left only): lens facing the board edge (the inner edge by the USB port)
   - diodes D1-D30: the cathode band on the same end as the band in the board's printed diode symbol
   - Q1, Q2 (left only): the single pin on the opposite side from the two pins, matching the pads
   - B1 (reset), T1 (power switch): the button / slider facing the board edge. On the left order
     both needed turning in JLCPCB's viewer. Right board (checked 2026-11-10): rotate B1 and T1
     "left" once (90 degrees) each; then the slider and button stick out past the board edge.
5. Parts you solder yourself afterwards: 30 hot-swap sockets, the controller header strips,
   and the JST battery connector (all large, easy joints).

## Known build note (both boards)
The hot-swap socket S30, under the controller's GND/RST/VCC pins, overlaps the controller's bottom
header strip by about 0.45 mm. File ~0.5 mm off the header strip's plastic edge there so it sits flat.

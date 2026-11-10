# Cirrus left PCB (work in progress)

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

The right half is unchanged from the original Caldera design (`../ergogen/output/pcbs/`).

## New parts (all on the back, all assembled by JLCPCB)
| Ref | Part | JLCPCB # | Job |
|---|---|---|---|
| LED1 | SK6812SIDE-A-RVS | C2890037 | status LED, data from P0.06 |
| Q1 | DMG1013UW (P-MOSFET, SOT-323) | C3040603 | switches battery (RAW) to the LED |
| Q2 | 2N7002WT1G (N-MOSFET, SOT-323) | C232391 | lets P0.08 drive Q1 |
| R1 | 100k 0402 | C25741 | keeps Q1 off by default |
| R2 | 100k 0402 | C25741 | keeps Q2 off while the controller boots |
| C1 | 100nF 0402 | C1525 | LED power smoothing |

Firmware: P0.08 HIGH = LED powered; LED data on P0.06 (Pro Micro pin 1).

## Known build note
The hot-swap socket under the controller's GND/RST/VCC pins overlaps the controller's bottom
header strip by 0.43 mm. File ~0.5 mm off the header strip's plastic edge there so it sits flat.

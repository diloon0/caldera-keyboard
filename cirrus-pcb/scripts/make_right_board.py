"""Build the Cirrus right PCB from the original (v1) right board: the only change is the
printed board name (Caldera -> Cirrus). Run with KiCad's Python, from the cirrus-pcb folder:
  "C:\Program Files\KiCad\10.0\bin\python.exe" scripts\make_right_board.py ..\ergogen\output\pcbs\right_finished.kicad_pcb
Writes base\right_v1_kicad10.kicad_pcb (the original, upgraded to KiCad 10 format, untouched)
and cirrus_right.kicad_pcb."""
import os, sys, pcbnew

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = sys.argv[1]

b = pcbnew.LoadBoard(src)
base = os.path.join(ROOT, "base", "right_v1_kicad10.kicad_pcb")
b.Save(base)
print("saved original (KiCad 10 format):", base)

renamed = 0
for d in b.GetDrawings():
    if d.GetClass() == "PCB_TEXT" and d.GetText() == "Caldera":
        d.SetText("Cirrus"); renamed += 1
        print("board text: Caldera -> Cirrus at", pcbnew.ToMM(d.GetPosition().x), pcbnew.ToMM(d.GetPosition().y))
assert renamed == 1, renamed
out = os.path.join(ROOT, "cirrus_right.kicad_pcb")
b.Save(out)
print("saved", out)

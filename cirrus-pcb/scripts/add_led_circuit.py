"""Build the Cirrus left PCB from the original (v1) left board:
renames the printed board text, then places the status LED + power switch parts on the back
and routes them.
usage (KiCad's Python): python add_led_circuit.py base/left_v1_kicad10.kicad_pcb cirrus_left.kicad_pcb cirrus.pretty"""
import os, sys, pcbnew
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from router import Router, add_route

src, dst, mylib = sys.argv[1], sys.argv[2], sys.argv[3]
KLIB = r"C:\Program Files\KiCad\10.0\share\kicad\footprints"
b = pcbnew.LoadBoard(src)
mm = pcbnew.FromMM

# The keyboard is now called Cirrus: change the name printed on the board
for d in b.GetDrawings():
    if d.GetClass() == "PCB_TEXT" and d.GetText() == "Caldera":
        d.SetText("Cirrus")
        print("board text: Caldera -> Cirrus at", pcbnew.ToMM(d.GetPosition().x), pcbnew.ToMM(d.GetPosition().y))

def net(name):
    n = b.FindNet(name)
    if n is None:
        n = pcbnew.NETINFO_ITEM(b, name); b.Add(n)
    return n

PARTS = [
    ("LED1", mylib, "SK6812SIDE-A-RVS", "SK6812SIDE-A-RVS", "C2890037", 203.6, 69.8, -90,
        {"1": "P006", "2": "LED_VDD", "3": "", "4": "GND"}),
    ("Q1", KLIB + r"\Package_TO_SOT_SMD.pretty", "SOT-323_SC-70", "DMG1013UW", "C3040603", 198.9, 67.15, 180,
        {"1": "LED_GATE", "2": "RAW", "3": "LED_VDD"}),
    ("Q2", KLIB + r"\Package_TO_SOT_SMD.pretty", "SOT-323_SC-70", "2N7002WT1G", "C232391", 195.0, 67.15, 0,
        {"1": "P008", "2": "GND", "3": "LED_GATE"}),
    ("R1", KLIB + r"\Resistor_SMD.pretty", "R_0402_1005Metric", "100k", "C25741", 201.35, 67.15, 90,
        {"1": "RAW", "2": "LED_GATE"}),
    ("R2", KLIB + r"\Resistor_SMD.pretty", "R_0402_1005Metric", "100k", "C25741", 192.6, 67.2, 90,
        {"1": "P008", "2": "GND"}),
    ("C1", KLIB + r"\Capacitor_SMD.pretty", "C_0402_1005Metric", "100nF", "C1525", 201.3, 70.6, 0,
        {"1": "LED_VDD", "2": "GND"}),
]
refs = [p[0] for p in PARTS]
for f in list(b.GetFootprints()):
    if f.GetReference() in refs: b.Remove(f)
for t in list(b.GetTracks()):
    if t.GetNetname() in ("LED_VDD", "LED_GATE"): b.Remove(t)

placed = {}
for ref, lib, fpname, value, lcsc, x, y, rot, padnets in PARTS:
    fp = pcbnew.FootprintLoad(lib, fpname); assert fp is not None, (lib, fpname)
    fp.SetReference(ref); fp.SetValue(value)
    fp.Reference().SetVisible(False)   # too crowded for printed labels; still shown on fab drawings
    b.Add(fp)
    fp.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
    fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    fp.SetOrientationDegrees(rot)
    try:
        f = pcbnew.PCB_FIELD(fp, pcbnew.FIELD_T_USER, "LCSC"); f.SetText(lcsc); f.SetVisible(False); fp.Add(f)
    except Exception as e:
        print("LCSC field not set:", e)
    for pad in fp.Pads():
        n = padnets.get(pad.GetNumber(), "")
        if n: pad.SetNet(net(n))
    placed[ref] = fp

def padxy(ref, num):
    fp = placed.get(ref) or [f for f in b.GetFootprints() if f.GetReference() == ref][0]
    pads = [p for p in fp.Pads() if p.GetNumber() == num]
    p = max(pads, key=lambda p: p.GetSize().x * p.GetSize().y)   # main pad (LED has tab pads)
    return (pcbnew.ToMM(p.GetPosition().x), pcbnew.ToMM(p.GetPosition().y))

for ref in refs:
    print(ref, [(p.GetNumber(), round(pcbnew.ToMM(p.GetPosition().x), 2), round(pcbnew.ToMM(p.GetPosition().y), 2), p.GetNetname()) for p in placed[ref].Pads()])

TH = ["F.Cu", "B.Cu"]; BK = ["B.Cu"]
# (net, from (ref,pad), to (ref,pad), from layers, to layers)
CONNS = [
    ("RAW",      ("MCU1", "24"), ("Q1", "2"),   TH, BK),
    ("RAW",      ("R1", "1"),    ("Q1", "2"),   BK, BK),
    ("LED_GATE", ("Q2", "3"),    ("Q1", "1"),   BK, BK),
    ("LED_GATE", ("R1", "2"),    ("Q1", "1"),   BK, BK),
    ("P008",     ("MCU1", "2"),  ("Q2", "1"),   TH, BK),
    ("P008",     ("R2", "1"),    ("Q2", "1"),   BK, BK),
    ("GND",      ("Q2", "2"),    ("MCU1", "3"), BK, TH),
    ("GND",      ("R2", "2"),    ("Q2", "2"),   BK, BK),
    ("LED_VDD",  ("Q1", "3"),    ("LED1", "2"), BK, BK),
    ("LED_VDD",  ("C1", "1"),    ("LED1", "2"), BK, BK),
    ("P006",     ("MCU1", "1"),  ("LED1", "1"), TH, BK),
    ("GND",      ("LED1", "4"),  ("C1", "2"),   BK, BK),
    ("GND",      ("C1", "2"),    ("MCU1", "3"), BK, TH),
]
ok = True
for netname, (ra, pa), (rb, pb), la, lb in CONNS:
    r = Router(b, 186.0, 64.5, 205.0, 100.0)
    path = r.route(netname, padxy(ra, pa), [padxy(rb, pb)], la, lb)
    if not path:
        print("FAILED", netname, ra, pa, "->", rb, pb); ok = False; continue
    parts = r.simplify(path)
    # snap first/last points exactly onto pad centres
    sx, sy = padxy(ra, pa); ex, ey = padxy(rb, pb)
    segs = [p for p in parts if p[0] == "seg"]
    if segs:
        i0 = parts.index(segs[0]); parts[i0] = ("seg", segs[0][1], (sx, sy), segs[0][3])
        i1 = parts.index(segs[-1]) if len(segs) > 1 else i0
        p1 = parts[i1]; parts[i1] = ("seg", p1[1], p1[2], (ex, ey))
    add_route(b, netname, parts)
    print("routed", netname, ra, pa, "->", rb, pb, ":", len([p for p in parts if p[0] == 'seg']), "segs,",
          len([p for p in parts if p[0] == 'via']), "vias")
b.Save(dst)
print("ALL ROUTED" if ok else "SOME FAILED")

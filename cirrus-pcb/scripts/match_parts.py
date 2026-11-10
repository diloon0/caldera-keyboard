"""For the original (Ergogen) parts whose pads are on the back but whose footprints are marked
front-side, find the standard KiCad library footprint + bottom-side orientation whose pads land
on the same copper. (KiCad Python.)

usage: python match_parts.py board.kicad_pcb            -> prints fit for a few sample parts
       import match_parts; match_parts.placements(board)  -> [(ref, lib, name, x_mm, y_mm, rot, err_mm)]"""
import sys, math, pcbnew

KLIB = r"C:\Program Files\KiCad\10.0\share\kicad\footprints"
CANDIDATES = {
    "ComboDiode": [("Diode_SMD", "D_SOD-123")],
    "Panasonic_EVQPUL_EVQPUC": [("Button_Switch_SMD", "Panasonic_EVQPUL_EVQPUC")],
    "SPDT_C128955": [("Button_Switch_SMD", "SW_SPDT_Shouhan_MSK12C02"), ("Button_Switch_SMD", "SW_SPDT_PCM12")],
}

def back_smd_pads(fp):
    return [(str(p.GetNumber()), p.GetPosition().x, p.GetPosition().y) for p in fp.Pads()
            if p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD and p.IsOnLayer(pcbnew.B_Cu)]

def fit(target, cand):
    """mean distance from each numbered target pad to the nearest same-numbered candidate pad"""
    tot, n = 0.0, 0
    for num, x, y in target:
        same = [(qx, qy) for (m, qx, qy) in cand if m == num]
        if not same: return 1e9
        tot += min(math.hypot(x - qx, y - qy) for qx, qy in same); n += 1
    return tot / max(n, 1) / 1e6

def best(tmp, target, lib, name):
    numbered = [t for t in target if t[0]]
    cx = sum(t[1] for t in target) / len(target); cy = sum(t[2] for t in target) / len(target)
    res = None; keep = []
    for rot in range(0, 360, 90):
        c = pcbnew.FootprintLoad(KLIB + "\\" + lib + ".pretty", name)
        tmp.Add(c)
        c.SetPosition(pcbnew.VECTOR2I(int(cx), int(cy)))
        c.Flip(c.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        c.SetOrientationDegrees(rot)
        cp = back_smd_pads(c)
        ccx = sum(t[1] for t in cp) / len(cp); ccy = sum(t[2] for t in cp) / len(cp)
        c.Move(pcbnew.VECTOR2I(int(cx - ccx), int(cy - ccy)))
        err = fit(numbered, back_smd_pads(c))
        if res is None or err < res[0]:
            res = (err, rot, pcbnew.ToMM(c.GetPosition().x), pcbnew.ToMM(c.GetPosition().y))
        keep.append(c)  # leave on the throwaway board copy (removing breaks the Python wrapper)
    return res

def placements(board, refs=None):
    out = []
    targets = []
    for fp in board.GetFootprints():
        key = str(fp.GetFPIDAsString()).split(":")[-1]
        if key in CANDIDATES and (refs is None or str(fp.GetReference()) in refs):
            targets.append((str(fp.GetReference()), key, back_smd_pads(fp)))
    for ref, key, target in targets:
        fits = [(best(board, target, lib, name), lib, name) for lib, name in CANDIDATES[key]]
        (err, rot, x, y), lib, name = min(fits, key=lambda f: f[0][0])
        out.append((ref, lib, name, x, y, rot, err, [(n2, best_err[0]) for best_err, l2, n2 in fits]))
    return out

if __name__ == "__main__":
    b = pcbnew.LoadBoard(sys.argv[1])
    for ref, lib, name, x, y, rot, err, alts in placements(b, {"D1", "D7", "D30", "B1", "T1"}):
        print(f"{ref:4s} best: {name:28s} mean pad error {err:.3f} mm -> bottom rot {rot}, at ({x:.3f}, {y:.3f})   all: {[(n, round(e, 3)) for n, e in alts]}")

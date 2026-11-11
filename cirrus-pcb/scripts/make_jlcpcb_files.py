"""Make the JLCPCB order files for a Cirrus board (left or right).
Run with KiCad's Python from the cirrus-pcb folder:
  "C:\\Program Files\\KiCad\\10.0\\bin\\python.exe" scripts\\make_jlcpcb_files.py left
  "C:\\Program Files\\KiCad\\10.0\\bin\\python.exe" scripts\\make_jlcpcb_files.py right
Outputs (in jlcpcb/; SIDE = left or right):
  cirrus_SIDE_gerbers.zip   board layers + drill files (upload as the PCB)
  cirrus_SIDE_bom.csv       parts list with JLCPCB part numbers
  cirrus_SIDE_cpl.csv       placement file (position, rotation, side of every assembled part)
  gerbers_SIDE/             the same gerbers unzipped, for looking at
Parts NOT assembled by JLCPCB (you solder them): hot-swap sockets S1-S30, controller sockets
(MCU1), battery connector JST1."""
import os, sys, csv, shutil, subprocess, zipfile, pcbnew
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import match_parts

KICAD_CLI = r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe"
ROOT = os.path.dirname(HERE)
SIDE = sys.argv[1] if len(sys.argv) > 1 else "left"
if SIDE not in ("left", "right"): raise SystemExit("usage: make_jlcpcb_files.py left|right")
NAME = "cirrus_" + SIDE
BOARD = os.path.join(ROOT, NAME + ".kicad_pcb")
OUT = os.path.join(ROOT, "jlcpcb")

# What JLCPCB places, keyed by reference prefix/name -> (comment, JLCPCB part #)
PARTS = {
    "D":    ("1N4148W", "C81598"),
    "B1":   ("EVQPUC02K reset button", "C79174"),
    "T1":   ("K3-1296S-E1 power slide switch", "C128955"),
    "LED1": ("SK6812SIDE-A-RVS", "C2890037"),
    "Q1":   ("DMG1013UW", "C3040603"),
    "Q2":   ("2N7002WT1G", "C232391"),
    "R1":   ("100k", "C25741"),
    "R2":   ("100k", "C25741"),
    "C1":   ("100nF", "C1525"),
}

def part_for(ref):
    if ref in PARTS: return PARTS[ref]
    if ref.startswith("D") and ref[1:].isdigit(): return PARTS["D"]
    return None

def run(*args):
    r = subprocess.run([KICAD_CLI, *args], capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout, r.stderr); raise SystemExit("kicad-cli failed: " + " ".join(args))

def main():
    gdir = os.path.join(OUT, "gerbers_" + SIDE)   # only this side's files are replaced
    if os.path.isdir(gdir): shutil.rmtree(gdir)
    os.makedirs(gdir)

    # 1) Gerbers + drill (JLCPCB's recommended KiCad settings)
    run("pcb", "export", "gerbers", "-o", gdir + os.sep,
        "-l", "F.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts",
        "--subtract-soldermask", "--no-x2", "--no-netlist", BOARD)
    run("pcb", "export", "drill", "-o", gdir + os.sep, "--format", "excellon", "--excellon-units", "mm",
        "--excellon-zeros-format", "decimal", "--excellon-oval-format", "alternate", BOARD)
    zpath = os.path.join(OUT, NAME + "_gerbers.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(os.listdir(gdir)):
            z.write(os.path.join(gdir, f), f)

    # 2) Placement: a throwaway copy of the board where the original Ergogen parts (marked
    #    front-side but with pads on the back) are swapped for the matching standard KiCad
    #    library footprints on the back, so KiCad's own exporter reports side + rotation.
    b = pcbnew.LoadBoard(BOARD)
    swaps = match_parts.placements(b)
    by_ref = {f.GetReference(): f for f in b.GetFootprints()}
    for ref, lib, name, x, y, rot, err, _ in swaps:
        if err > 0.15: raise SystemExit(f"{ref}: library footprint {name} doesn't fit ({err:.3f} mm)")
        orig = by_ref[ref]
        c = pcbnew.FootprintLoad(os.path.join(match_parts.KLIB, lib + ".pretty"), name)
        b.Add(c)
        c.SetReference(ref)
        c.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y)))
        c.Flip(c.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        c.SetOrientationDegrees(rot)
        orig.SetReference(ref + "_orig")
    tmp = os.path.join(OUT, "_placement_tmp.kicad_pcb")
    b.Save(tmp)
    pos = os.path.join(OUT, "_pos.csv")
    run("pcb", "export", "pos", "--side", "both", "--format", "csv", "--units", "mm", "-o", pos, tmp)

    rows = []
    with open(pos, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            p = part_for(r["Ref"])
            if p is None: continue           # not assembled by JLCPCB
            rows.append(r)
    with open(os.path.join(OUT, NAME + "_cpl.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for r in sorted(rows, key=lambda r: (r["Ref"].rstrip("0123456789"), int("0" + "".join(ch for ch in r["Ref"] if ch.isdigit())))):
            w.writerow([r["Ref"], f'{float(r["PosX"]):.4f}mm', f'{float(r["PosY"]):.4f}mm',
                        r["Side"].capitalize(), f'{float(r["Rot"]) % 360:.0f}'])

    # 3) BOM grouped by JLCPCB part
    groups = {}
    for r in rows:
        comment, lcsc = part_for(r["Ref"])
        g = groups.setdefault(lcsc, {"comment": comment, "refs": [], "pkg": r["Package"]})
        g["refs"].append(r["Ref"])
    with open(os.path.join(OUT, NAME + "_bom.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["Comment", "Designator", "Footprint", "JLCPCB Part #"])
        for lcsc, g in groups.items():
            refs = sorted(g["refs"], key=lambda s: (s.rstrip("0123456789"), int("0" + "".join(ch for ch in s if ch.isdigit()))))
            w.writerow([g["comment"], ",".join(refs), g["pkg"], lcsc])

    for f in (tmp, pos): os.remove(f)
    for f in os.listdir(OUT):
        if f.startswith("_placement_tmp"): os.remove(os.path.join(OUT, f))
    print("wrote", sorted(f for f in os.listdir(OUT) if SIDE in f))
    print("assembled parts:", len(rows), "| BOM lines:", len(groups))

if __name__ == "__main__":
    main()

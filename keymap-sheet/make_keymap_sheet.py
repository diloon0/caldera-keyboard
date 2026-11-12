"""Draw a printable reference sheet of the Cirrus keymap.

Reads config/cirrus.keymap (the bindings) and config/cirrus.json (where each key sits), and writes
  keymap-sheet/cirrus-keymap.html   (open in a browser; Ctrl+P prints it)
  keymap-sheet/cirrus-keymap.pdf    (if Microsoft Edge or Chrome is installed)

usage (any Python 3, no extra packages):  python keymap-sheet/make_keymap_sheet.py

Re-run it after changing the keymap. Keys it doesn't know get their raw ZMK name; add a nicer
name to KEY_NAMES or BEHAVIORS below. Note: changes made in ZMK Studio live on the keyboard,
not in the keymap file, so they won't show up here.
"""
import html, json, os, pathlib, re, shutil, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

# ---------------------------------------------------------------- what to draw
# (layer node name, title, how to get there). Layers not listed are skipped.
PAGES = [
    [("default_layer", "Base", "Normal typing. Colored keys lead to the other layers (colors match the status light)."),
     ("layer_lock", "Layer Lock",
      "TAP the Thumb key, then press ONE key below. It does that one thing and Layer Lock ends. "
      "Gray keys just type normally.")],
    [("num_pad", "Numpad", "HOLD Thumb or Num. To keep it on: tap Num (or Layer Lock, then Num). Go home turns it off."),
     ("arrows_media", "Nav / Media", "HOLD Nav. To keep it on: tap Nav (or Layer Lock, then Nav). Go home turns it off.")],
    [("system", "System",
      "Layer Lock, then B. Do ONE thing, then it closes by itself (or after 5 s). Blank keys do nothing.")],
]

# Colors per layer (same as the status light)
LAYER_COLOR = {"NUMPAD": "#bfe8b5", "NAV": "#ffe58a", "SYS": "#a9e3ee", "LOCK": "#f3b6e7",
               "WORD": "#ffc994", "CC_TEST": "#d8c4f5"}
LAYER_NAME = {"NUMPAD": "Numpad", "NAV": "Nav", "SYS": "System", "LOCK": "Layer Lock",
              "WORD": "Word-delete", "CC_TEST": "HID Test"}

# ---------------------------------------------------------------- key names
KEY_NAMES = {
    "ESCAPE": "Esc", "TAB": "Tab", "CAPSLOCK": "Caps Lock", "LSHFT": "Shift", "RIGHT_SHIFT": "Shift",
    "LCTRL": "Ctrl", "LALT": "Alt", "RIGHT_ALT": "AltGr", "LMETA": "Win", "SPACE": "Space",
    "RET": "Enter", "APOS": "'", "SEMI": ";", "COMMA": ",", "DOT": ".", "PERIOD": ".", "FSLH": "/",
    "SLASH": "/", "MINUS": "-", "K_APP": "Menu", "GRAVE": "`", "ASTRK": "*", "PIPE": "|",
    "PLUS": "+", "BSLH": "\\", "EQUAL": "=", "LEFT_BRACKET": "[", "RIGHT_BRACKET": "]",
    "LEFT_BRACE": "{", "RIGHT_BRACE": "}", "HOME": "Home", "END": "End", "PAGE_UP": "Page Up",
    "PAGE_DOWN": "Page Down", "KP_NUMLOCK": "Num Lock", "PRINTSCREEN": "Print Screen", "SCROLLLOCK": "Scroll Lock", "DEL": "Delete",
    "UP": "\u2191", "DOWN": "\u2193", "LEFT": "\u2190", "RIGHT": "\u2192",
    "C_PREV": "Prev track", "C_NEXT": "Next track", "C_PP": "Play / Pause", "C_VOL_UP": "Vol +",
    "C_VOL_DN": "Vol \u2212", "C_MUTE": "Mute",
    "K_SLEEP": "Sleep (A)", "C_SLEEP": "Sleep (B)", "C_SLEEP_MODE": "Sleep (C)",
    "LC(B)": "Bold", "LC(I)": "Italic", "LC(U)": "Underline", "LC(A)": "Select all", "LC(S)": "Save",
    "RC(Z)": "Undo", "RC(X)": "Cut", "RC(C)": "Copy", "RC(V)": "Paste",
    "RC(TAB)": "Next tab", "RC(RS(TAB))": "Prev tab", "LC(DEL)": "Delete word",
}
for i in range(10): KEY_NAMES[f"N{i}"] = str(i)
for i in range(1, 13): KEY_NAMES[f"F{i}"] = f"F{i}"
SUBTITLE = {"LC(B)": "Ctrl+B", "LC(I)": "Ctrl+I", "LC(U)": "Ctrl+U", "LC(A)": "Ctrl+A", "LC(S)": "Ctrl+S",
            "RC(Z)": "Ctrl+Z", "RC(X)": "Ctrl+X", "RC(C)": "Ctrl+C", "RC(V)": "Ctrl+V"}

def key_name(code):
    if code in KEY_NAMES: return KEY_NAMES[code]
    if len(code) == 1: return code
    return code.replace("_", " ")

def label(binding):
    """-> dict(top=main text, sub=small text, cls=style, color=fill or None)"""
    parts = binding.split()
    b, args = parts[0], parts[1:]
    L = lambda top, sub="", cls="", color=None: dict(top=top, sub=sub, cls=cls, color=color)
    if b == "&kp": return L(key_name(args[0]), SUBTITLE.get(args[0], ""))
    if b == "&trans": return L("", "", "trans")
    if b == "&none": return L("", "", "none")
    if re.fullmatch(r"&ac\d", b): return L(b[-1])          # numpad digit (keypad digit while Alt is held)
    if b == "&bspc_del": return L("Backspace", "Shift: Delete")
    if b == "&word_bspc_del": return L("Delete word", "Shift: next word")
    if b == "&go_home": return L("Go home", "locked layers off")
    if b == "&layer_mo_sticky":          # hold = args[0], tap = sticky args[1]
        return L("Thumb", f"hold: {LAYER_NAME[args[0]]}\ntap: Lock layer", "", LAYER_COLOR[args[1]])
    if b == "&layer_mo_lock":
        n = LAYER_NAME[args[0]]
        return L("Num" if args[0] == "NUMPAD" else n, f"hold: {n}\ntap: lock on", "", LAYER_COLOR[args[0]])
    if b == "&specialtab": return L("Alt+Tab", "hold to browse")
    if b == "&caps_word": return L("Caps Word", "one word")
    if b == "&msc": return L({"SCRL_UP": "Scroll \u2191", "SCRL_DOWN": "Scroll \u2193"}.get(args[0], args[0]))
    if b == "&lock_tog":
        if args[0] == "WORD": return L("Word-delete", "on / off", "", LAYER_COLOR["WORD"])
        return L(LAYER_NAME[args[0]], "lock on / off", "", LAYER_COLOR[args[0]])
    if b == "&lock_sys": return L("System", "one action", "", LAYER_COLOR["SYS"])
    if b == "&lock_bt_tog": return L("BT 1 \u21c4 2", "switch device")
    if b == "&bootloader": return L("Flash mode", "this half", "warn")
    if b == "&sys_bt":
        if args[0] == "BT_SEL": return L(f"BT {int(args[1]) + 1}", "device")
        if args[0] == "BT_CLR": return L("Forget", "this device", "warn")
    if b == "&sys_out": return L({"OUT_USB": "Use USB", "OUT_BLE": "Use BT"}.get(args[0], args[0]))
    if b == "&sys_unlock": return L("Studio", "unlock")
    if b in ("&mo", "&tog", "&sl"): return L(LAYER_NAME.get(args[0], args[0]), b[1:], "", LAYER_COLOR.get(args[0]))
    return L(binding.lstrip("&"))

# ---------------------------------------------------------------- read the config
def read_layers():
    text = open(os.path.join(REPO, "config", "cirrus.keymap"), encoding="utf-8").read()
    text = re.sub(r"//[^\n]*", "", text)
    layers = {}
    for m in re.finditer(r"(\w+)\s*\{\s*display-name\s*=\s*\"[^\"]*\";\s*bindings\s*=\s*<(.*?)>;", text, re.S):
        binds = [" ".join(t.split()) for t in re.findall(r"&[^&]+", m.group(2))]
        layers[m.group(1)] = binds
    return layers

def read_positions():
    d = json.load(open(os.path.join(REPO, "config", "cirrus.json"), encoding="utf-8"))
    return [(k["x"], k["y"]) for k in d["layouts"]["default_transform"]["layout"]]

# ---------------------------------------------------------------- drawing
U = 54          # px per key unit in the SVG
GAP = 3         # px between keys

def wrap(text, maxch):
    words, lines, cur = text.split(" "), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > maxch: lines.append(cur); cur = w
        else: cur = (cur + " " + w).strip()
    if cur: lines.append(cur)
    return lines

def key_svg(x, y, lab, base_lab, held):
    px, py = x * U, y * U
    w = h = U - GAP
    cls, fill, stroke, sw = lab["cls"], "#ffffff", "#9aa0a8", 1
    top, sub = lab["top"], lab["sub"]
    tcolor = "#1d1f23"
    if lab["color"]: fill = lab["color"]
    if cls == "trans":                      # falls through to the Base layer: show it faded
        top, sub, fill, tcolor = base_lab["top"], "", "#f1f2f4", "#a3a8b0"
        if base_lab["color"]: top = base_lab["top"]
    if cls == "none": fill = "#e4e6e9"
    if cls == "warn": fill, stroke = "#fde2e2", "#d9534f"
    if held: fill, stroke, sw = "#3b3f46", "#3b3f46", 1; top, sub, tcolor = "HELD", "", "#ffffff"
    out = [f'<rect x="{px:.1f}" y="{py:.1f}" width="{w}" height="{h}" rx="6" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>']
    cx = px + w / 2
    lines = []
    if top:
        tl = wrap(top, 9)
        size = 15 if max(len(t) for t in tl) <= 3 else 11.5 if max(len(t) for t in tl) <= 7 else 10
        lines += [(t, size, "600" if cls != "trans" else "400", tcolor) for t in tl]
    if sub:
        for s in sub.split("\n"):
            lines += [(t, 7.5, "400", "#4a4f57") for t in wrap(s, 15)]
    total = sum(l[1] * 1.15 for l in lines)
    yy = py + h / 2 - total / 2
    for t, size, weight, col in lines:
        yy += size * 1.15
        out.append(f'<text x="{cx:.1f}" y="{yy - size * 0.25:.1f}" font-size="{size}" font-weight="{weight}" '
                   f'fill="{col}" text-anchor="middle">{html.escape(t)}</text>')
    return "\n".join(out)

def layer_svg(binds, base, pos, held=()):
    xs = [p[0] for p in pos]; ys = [p[1] for p in pos]
    x0, y0 = min(xs), min(ys)
    W = (max(xs) - x0 + 1) * U; H = (max(ys) - y0 + 1) * U
    keys = []
    for i, (b, (x, y)) in enumerate(zip(binds, pos)):
        lab = label(b)
        if b == "&bootloader": lab["sub"] = "LEFT half" if i % 12 < 6 else "RIGHT half"
        keys.append(key_svg(x - x0, y - y0, lab, label(base[i]), i in held))
    return (f'<svg viewBox="-2 -2 {W + 4:.0f} {H + 4:.0f}" xmlns="http://www.w3.org/2000/svg" '
            f'font-family="Segoe UI, Arial, sans-serif">' + "\n".join(keys) + "</svg>")

def held_keys(name, base):
    """keys you hold to reach a layer: show them as HELD on that layer"""
    target = {"num_pad": "NUMPAD", "arrows_media": "NAV"}.get(name)
    if not target: return set()
    return {i for i, b in enumerate(base)
            if b.split()[0] in ("&layer_mo_sticky", "&layer_mo_lock") and b.split()[1] == target}

CSS = """
@page { size: letter landscape; margin: 0.35in; }
body { font-family: "Segoe UI", Arial, sans-serif; color: #1d1f23; margin: 0; background: #fff; }
.page { page-break-after: always; break-after: page; }
.page:last-child { page-break-after: auto; break-after: auto; }
.layer { margin: 0 0 0.18in 0; break-inside: avoid; page-break-inside: avoid; }
h2 { font-size: 15pt; margin: 0 0 2pt 0; }
h2 span.chip { display: inline-block; width: 12pt; height: 12pt; border-radius: 3pt; vertical-align: -1pt; margin-right: 5pt; border: 1px solid #9aa0a8; }
p.how { font-size: 9.5pt; margin: 0 0 4pt 0; color: #3b3f46; }
svg { display: block; height: 3.0in; width: auto; max-width: 100%; margin: 2pt auto 0 auto; }
.notes { font-size: 9.5pt; line-height: 1.35; columns: 2; column-gap: 0.4in; margin-top: 0.1in; }
.notes h3 { font-size: 11pt; margin: 0 0 3pt 0; break-after: avoid; }
.notes div { break-inside: avoid; margin-bottom: 8pt; }
.legend span { display: inline-block; padding: 1pt 6pt; border-radius: 3pt; border: 1px solid #9aa0a8; margin: 0 4pt 3pt 0; font-size: 9pt; }
@media screen { body { background: #e9ebee; } .page { background: #fff; width: 10.3in; margin: 0.3in auto; padding: 0.35in; box-shadow: 0 1px 4px rgba(0,0,0,.2); } }
"""

NOTES = """
<div class="notes">
<div><h3>Key colors</h3><div class="legend">
<span style="background:#f3b6e7">Layer Lock</span><span style="background:#bfe8b5">Numpad</span>
<span style="background:#ffe58a">Nav</span><span style="background:#a9e3ee">System</span>
<span style="background:#ffc994">Word-delete</span><span style="background:#f1f2f4;color:#a3a8b0">gray = types like Base</span>
<span style="background:#e4e6e9">blank = off</span><span style="background:#fde2e2;border-color:#d9534f">red = careful</span>
</div>The status light uses the same colors (white = Caps Lock).</div>
<div><h3>Word-delete mode</h3>Turn on/off: tap <b>Thumb</b>, then <b>Backspace</b>.<br>
While on: Backspace deletes the previous word, Shift+Backspace the next word, and Nav's Delete
deletes the next word. Numpad's Backspace still deletes one character. Starts off after
waking or power-on.</div>
<div><h3>Alt codes (Windows)</h3>Hold <b>Thumb</b> (Numpad), hold <b>Alt</b> (its usual spot), type the code on the
number keys, let go of Alt. Example: Alt 0176 = &deg;, Alt 0151 = &mdash;. If a code moves the cursor
instead, tap <b>Num Lock</b> (Esc spot) once and try again.</div>
<div><h3>Flashing new firmware</h3>Plug that half in by USB. Layer Lock, B, then the <b>Flash mode</b> key
for that half (Esc spot = left, Backspace spot = right). A drive appears: copy the .uf2 file onto it.</div>
<div><h3>Bluetooth</h3>Quick switch between devices 1 and 2: tap <b>Thumb</b>, then <b>Tab</b>.
Devices 1-5 and "Forget": System layer. The status light blinks blue: 1 blink = device 1, 2 = device 2.</div>
</div>
"""

def main():
    layers = read_layers(); pos = read_positions()
    base = layers["default_layer"]
    for name, binds in layers.items():
        assert len(binds) == len(pos), f"{name}: {len(binds)} keys, expected {len(pos)}"
    pages = []
    for page in PAGES:
        parts = []
        for name, title, how in page:
            color = {"layer_lock": LAYER_COLOR["LOCK"], "num_pad": LAYER_COLOR["NUMPAD"],
                     "arrows_media": LAYER_COLOR["NAV"], "system": LAYER_COLOR["SYS"]}.get(name, "#ffffff")
            parts.append(f'<div class="layer"><h2><span class="chip" style="background:{color}"></span>'
                         f'{html.escape(title)}</h2><p class="how">{html.escape(how)}</p>'
                         f'{layer_svg(layers[name], base, pos, held_keys(name, base))}</div>')
        if len(page) == 1: parts.append(NOTES)
        pages.append('<div class="page">' + "\n".join(parts) + "</div>")
    doc = ('<!doctype html><html><head><meta charset="utf-8"><title>Cirrus keymap</title>'
           f"<style>{CSS}</style></head><body>" + "\n".join(pages) + "</body></html>")
    out_html = os.path.join(HERE, "cirrus-keymap.html")
    open(out_html, "w", encoding="utf-8").write(doc)
    print("wrote", out_html)

    candidates = [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                  r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
                  r"C:\Program Files\Google\Chrome\Application\chrome.exe"]
    candidates += [shutil.which(n) or "" for n in ("msedge", "chrome", "google-chrome", "chromium", "chromium-browser")]
    browser = next((p for p in candidates if p and os.path.exists(p)), None)
    if browser:
        out_pdf = os.path.join(HERE, "cirrus-keymap.pdf")
        subprocess.run([browser, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                        f"--print-to-pdf={out_pdf}", pathlib.Path(out_html).as_uri()],
                       capture_output=True, timeout=120)
        print("wrote", out_pdf if os.path.exists(out_pdf) else "(PDF failed - print the HTML from a browser)")

if __name__ == "__main__":
    main()

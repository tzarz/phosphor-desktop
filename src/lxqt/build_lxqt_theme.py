import re, sys, pathlib, shutil

SRC = pathlib.Path("/usr/share/lxqt/themes/dark")
DST = pathlib.Path.home() / ".local/share/lxqt/themes/Matrix"

def green_from_lum(L):
    """Map a grey level to a phosphor-green of comparable luminance."""
    L = max(0, min(255, int(L)))
    return (int(L * 0.10), L, int(L * 0.26))

def conv_rgb(r, g, b):
    mx, mn = max(r, g, b), min(r, g, b)
    if mx - mn <= 8:                 # grey -> green tint
        return green_from_lum(mx)
    if r > g and r >= b:             # red accent -> swap R/G = green accent
        return (g, r, b)
    return (r, g, b)

def hex_sub(m):
    h = m.group(0)[1:]
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = (int(h[i:i+2], 16) for i in (0, 2, 4))
    return "#%02X%02X%02X" % conv_rgb(r, g, b)

def rgb_sub(m):
    fn, args = m.group(1), [a.strip() for a in m.group(2).split(",")]
    nums = [a for a in args]
    r, g, b = (int(nums[i]) for i in range(3))
    r, g, b = conv_rgb(r, g, b)
    rest = nums[3:]
    return "%s(%s)" % (fn, ", ".join([str(r), str(g), str(b)] + rest))

def hsv_sub(m):
    h, s, v = (int(x.strip()) for x in m.group(1).split(","))
    if s == 0:                       # greyscale hsv -> green
        r, g, b = green_from_lum(round(v * 255 / 100) if v <= 100 else v)
        return "rgb(%d, %d, %d)" % (r, g, b)
    return m.group(0)

HEX = re.compile(r"#[0-9A-Fa-f]{6}\b|#[0-9A-Fa-f]{3}\b")
RGB = re.compile(r"\b(rgba|rgb)\(([^)]*)\)")
HSV = re.compile(r"\bhsv\(([^)]*)\)")

if DST.exists():
    shutil.rmtree(DST)
shutil.copytree(SRC, DST)

changed = 0
for p in sorted(DST.rglob("*")):
    if not p.is_file() or p.suffix.lower() not in (".qss", ".cfg", ".svg"):
        continue
    try:
        t = p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        continue
    new = HSV.sub(hsv_sub, RGB.sub(rgb_sub, HEX.sub(hex_sub, t)))
    if new != t:
        p.write_text(new, encoding="utf-8")
        changed += 1
        print("recolored:", p.relative_to(DST))
# Papirus-style blue accent in the spacer plugin is not a grey, so the
# luminance rule above leaves it alone. Map it to a mid green explicitly.
for p in (DST / "spacer-plugin").glob("*.svg"):
    s = p.read_text(encoding="utf-8")
    if "#1A80BF" in s or "#1a80bf" in s:
        p.write_text(s.replace("#1A80BF", "#13BE31").replace("#1a80bf", "#13BE31"),
                     encoding="utf-8")
        print("recolored accent:", p.name)

print("\nfiles recolored:", changed)
print("theme at:", DST)

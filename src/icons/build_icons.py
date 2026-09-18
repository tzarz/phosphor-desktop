#!/usr/bin/python3
"""
Build the "Papirus-Phosphor" icon theme.

Two things happen here:

1. Folder / directory icons are DRAWN from scratch (see folder_svg.py) as
   outline line art: a near-black body with a phosphor-green outline and a
   faint glow. Papirus' own green folders are a muted olive (#87b158), which
   does not read as "Phosphor", so we do not reuse them.

2. Monochrome categories (actions, status, panel, emblems, animations) are
   copied from Papirus-Dark with their greys remapped to green of the same
   luminance. Colourful categories (apps, mimetypes, devices, categories) are
   deliberately left to inherit Papirus-Dark so applications stay recognisable.

Note: pcmanfm-qt asks for the icon name `inode-directory`, not `folder`. A
theme that overrides only `folder` silently falls through to the inherited
theme, so `inode-directory` is generated explicitly.
"""
import os, re, sys, shutil, pathlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from folder_svg import folder_svg, GLYPHS

SRC = pathlib.Path("/usr/share/icons/Papirus-Dark")
DST = pathlib.Path.home()/".local/share/icons/Papirus-Phosphor"

RECOLOR_CATS = {"actions", "status", "panel", "emblems", "animations"}
COLOR_WORDS = ("adwaita black blue bluegrey breeze brown carmine cyan darkcyan "
               "deeporange drag google green grey indigo magenta nordic orange "
               "palebrown paleorange pink red teal violet white yandex yaru "
               "yellow").split()

# icon-name keyword -> glyph in folder_svg.GLYPHS
GLYPH_RULES = [
    (("document", "text", "writer", "office", "paper"), "documents"),
    (("download",), "download"),
    (("music", "audio", "sound", "podcast"), "music"),
    (("picture", "image", "photo", "camera", "wallpaper", "screenshot"), "pictures"),
    (("video", "movie", "film"), "videos"),
    (("desktop",), "desktop"),
    (("home", "user-home"), "home"),
    (("code", "develop", "script", "vscode", "project", "java", "python"), "code"),
    (("git", "github", "gitlab"), "git"),
    (("template",), "templates"),
    (("remote", "network", "nfs", "samba", "cloud", "drive", "dropbox",
      "mega", "owncloud", "nextcloud", "ftp"), "remote"),
    (("public", "share"), "publicshare"),
    (("lock", "encrypt", "private", "secure", "vault"), "lock"),
    (("trash", "bin"), "trash"),
]

def glyph_for(name):
    n = name.lower()
    for words, g in GLYPH_RULES:
        if any(w in n for w in words):
            return g
    return None

def is_color_variant(name):
    m = re.match(r"folder-([a-z]+)(-|\.)", name)
    return bool(m and m.group(1) in COLOR_WORDS)

# ---------- grey -> green recolouring for monochrome categories ----------
def green_from_lum(L):
    L = max(0, min(255, int(L)))
    return (int(L*0.10), L, int(L*0.26))

def conv(r, g, b):
    if max(r, g, b) - min(r, g, b) <= 10:
        return green_from_lum(max(r, g, b))
    return (r, g, b)

HEX = re.compile(r"#([0-9A-Fa-f]{6})\b")
def hexsub(m):
    h = m.group(1)
    r, g, b = (int(h[i:i+2], 16) for i in (0, 2, 4))
    return "#%02X%02X%02X" % conv(r, g, b)


def main():
    if not SRC.is_dir():
        sys.exit("Papirus-Dark not found - install papirus-icon-theme first")
    if DST.exists():
        shutil.rmtree(DST)
    DST.mkdir(parents=True)

    provided, n_folder, n_recolor = [], 0, 0

    for size_dir in sorted(SRC.iterdir()):
        if not size_dir.is_dir():
            continue
        size = size_dir.name
        px = int(size.split("x")[0])

        # ---------------- folders: drawn, not recoloured ----------------
        places = size_dir/"places"
        if places.is_dir():
            out = DST/size/"places"
            out.mkdir(parents=True, exist_ok=True)
            names = set()
            for f in places.iterdir():
                n = f.name
                if not n.endswith(".svg"):
                    continue
                if n.startswith("folder") and not is_color_variant(n):
                    names.add(n)
                elif n.startswith("user-"):
                    names.add(n)
            names.update({"folder.svg", "folder-open.svg", "inode-directory.svg"})

            for n in sorted(names):
                stem = n[:-4]
                open_ = stem.endswith("-open")
                base = stem[:-5] if open_ else stem
                g = "home" if base == "inode-directory" and False else glyph_for(base)
                (out/n).write_text(folder_svg(px, g, open_=open_), encoding="utf-8")
                n_folder += 1
            provided.append(f"{size}/places")

        # ---------------- monochrome categories: recoloured ----------------
        for cat in sorted(RECOLOR_CATS):
            cdir = size_dir/cat
            if not cdir.is_dir():
                continue
            out = DST/size/cat
            out.mkdir(parents=True, exist_ok=True)
            wrote = 0
            for f in cdir.iterdir():
                if f.suffix != ".svg":
                    continue
                if f.is_symlink():
                    tgt = os.readlink(f)
                    link = out/f.name
                    if link.exists() or link.is_symlink():
                        link.unlink()
                    try:
                        link.symlink_to(tgt); wrote += 1
                    except OSError:
                        pass
                    continue
                try:
                    t = f.read_text(encoding="utf-8")
                except Exception:
                    continue
                (out/f.name).write_text(HEX.sub(hexsub, t), encoding="utf-8")
                wrote += 1; n_recolor += 1
            if wrote:
                provided.append(f"{size}/{cat}")
            else:
                shutil.rmtree(out, ignore_errors=True)

    lines = ["[Icon Theme]",
             "Name=Papirus-Phosphor",
             "Comment=Green outline folders and monochrome icons over Papirus-Dark",
             "Inherits=Papirus-Dark,breeze-dark,hicolor",
             "Example=folder",
             "FollowsColorScheme=true",
             "",
             "Directories=" + ",".join(provided), ""]
    for d in provided:
        s, cat = d.split("/")
        scale = "2" if s.endswith("@2x") else "1"
        sz = s[:-3] if s.endswith("@2x") else s
        lines += [f"[{d}]", f"Size={sz.split('x')[0]}", f"Scale={scale}",
                  f"Context={cat.capitalize()}", "Type=Fixed", ""]
    (DST/"index.theme").write_text("\n".join(lines), encoding="utf-8")

    print(f"folder icons drawn : {n_folder}")
    print(f"icons recoloured   : {n_recolor}")
    print(f"directories        : {len(provided)}")
    print(f"installed to       : {DST}")


if __name__ == "__main__":
    main()

#!/usr/bin/python3
"""Outline folder icons: near-black body, phosphor-green line art."""

GREEN      = "#19FF42"   # bright phosphor line
GREEN_DIM  = "#0E8F26"   # inner detail
GREEN_GLOW = "#19FF42"   # wide low-alpha stroke standing in for a glow
BODY       = "#020A03"   # near-black interior with a green cast

# Closed folder outline on a 48x48 canvas.
FOLDER = ("M 6,9 H 17 A 2,2 0 0 1 18.6,9.8 L 21,13 A 2,2 0 0 0 22.6,13.8 "
          "H 42 A 2,2 0 0 1 44,15.8 V 38 A 2,2 0 0 1 42,40 H 6 "
          "A 2,2 0 0 1 4,38 V 11 A 2,2 0 0 1 6,9 Z")

# Open folder: same back, with a slanted front panel.
FOLDER_BACK = ("M 6,9 H 17 A 2,2 0 0 1 18.6,9.8 L 21,13 A 2,2 0 0 0 22.6,13.8 "
               "H 40 A 2,2 0 0 1 42,15.8 V 22 H 12 L 6,38 V 9 Z")
FOLDER_FRONT = "M 4,38 L 10.5,22 H 46 L 39.5,38 A 2,2 0 0 1 37.6,40 H 6 Z"

GLYPHS = {
    "documents": '<path d="M17,20 H31 M17,25 H31 M17,30 H26"/>',
    "download":  '<path d="M24,19 V30 M19,26 l5,5 5,-5"/>',
    "music":     '<path d="M21,32 V21 l9,-2 v11"/><circle cx="19" cy="32" r="2.4"/>'
                 '<circle cx="28" cy="30" r="2.4"/>',
    "pictures":  '<path d="M16,32 l6,-8 4,5 3,-4 5,7 Z"/><circle cx="19" cy="22" r="2"/>',
    "videos":    '<path d="M21,20 l11,6 -11,6 Z"/>',
    "desktop":   '<path d="M16,20 H32 V30 H16 Z M21,34 H27 M24,30 v4"/>',
    "home":      '<path d="M17,26 l7,-7 7,7 M19,25 v8 h10 v-8"/>',
    "code":      '<path d="M20,21 l-5,5 5,5 M28,21 l5,5 -5,5"/>',
    "git":       '<path d="M20,21 v10 M20,26 h8 v-5"/><circle cx="20" cy="20" r="2"/>'
                 '<circle cx="20" cy="32" r="2"/><circle cx="28" cy="20" r="2"/>',
    "templates": '<path d="M16,20 H32 V32 H16 Z M16,25 H32 M22,25 V32"/>',
    "remote":    '<path d="M24,19 a8,8 0 0 1 0,16 a8,8 0 0 1 0,-16 M16,27 H32 '
                 'M24,19 a12,8 0 0 0 0,16 M24,19 a12,8 0 0 1 0,16"/>',
    "publicshare": '<path d="M19,26 a3,3 0 1 0 0.1,0 M29,21 a3,3 0 1 0 0.1,0 '
                   'M29,31 a3,3 0 1 0 0.1,0 M21.5,24.5 L26.5,22 M21.5,27.5 L26.5,30"/>',
    "lock":      '<path d="M19,26 H29 V34 H19 Z M21,26 v-3 a3,3 0 0 1 6,0 v3"/>',
    "trash":     '<path d="M18,22 H30 M20,22 V33 H28 V22 M22,25 v6 M26,25 v6"/>',
}


def folder_svg(size, glyph=None, open_=False):
    sw = 3.2 if size <= 24 else 2.4          # heavier line at small sizes
    gw = sw * 2.6
    detail = sw * 0.8
    glow = (f'<path d="{FOLDER}" fill="none" stroke="{GREEN_GLOW}" '
            f'stroke-width="{gw:.2f}" stroke-linejoin="round" opacity="0.13"/>')
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" '
             f'height="{size}" viewBox="0 0 48 48">']
    if open_:
        parts.append(f'<path d="{FOLDER_BACK}" fill="{BODY}" stroke="{GREEN_DIM}" '
                     f'stroke-width="{sw:.2f}" stroke-linejoin="round"/>')
        parts.append(f'<path d="{FOLDER_FRONT}" fill="{BODY}" fill-opacity="0.95" '
                     f'stroke="{GREEN}" stroke-width="{sw:.2f}" '
                     f'stroke-linejoin="round"/>')
    else:
        parts.append(glow)
        parts.append(f'<path d="{FOLDER}" fill="{BODY}" stroke="{GREEN}" '
                     f'stroke-width="{sw:.2f}" stroke-linejoin="round"/>')
        if size >= 32:
            parts.append(f'<path d="M 4.5,18.5 H 43.5" stroke="{GREEN_DIM}" '
                         f'stroke-width="{detail:.2f}" opacity="0.8"/>')
        if glyph and size >= 32:
            parts.append(f'<g fill="none" stroke="{GREEN}" '
                         f'stroke-width="{detail*1.5:.2f}" stroke-linecap="round" '
                         f'stroke-linejoin="round" opacity="0.95">{GLYPHS[glyph]}</g>')
    parts.append("</svg>")
    return "".join(parts)

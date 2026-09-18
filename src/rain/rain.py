#!/usr/bin/python3
"""
Flat 2D Phosphor digital rain as a live desktop background (X11 / LXQt / Openbox).

Design notes
------------
* One transparent GTK window per monitor, kept in the "below" layer, so it sits
  above pcmanfm-qt's desktop window but under every real window.
* The window uses an RGBA visual and is cleared to full alpha-0 each frame, so
  the wallpaper and desktop icons underneath remain visible between glyphs.
* An empty input shape makes the window click-through: desktop icons stay usable.
* Glyphs are pre-rendered once into an atlas of ImageSurfaces (char x brightness)
  and then blitted. No text shaping per frame -> low, flat CPU cost, no GPU work
  beyond the compositor blending one already-drawn surface.
"""

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk, GLib

import cairo
import random
import argparse
import os
import sys

KATAKANA = [chr(c) for c in range(0xFF66, 0xFF9E)]   # half-width katakana
DIGITS = list("0123456789")
LATIN = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
SYMBOLS = list("=+*<>|:-.^~")


def build_charset(mix):
    cs = []
    if "katakana" in mix:
        cs += KATAKANA * 3
    if "digits" in mix:
        cs += DIGITS * 2
    if "latin" in mix:
        cs += LATIN
    if "symbols" in mix:
        cs += SYMBOLS
    return cs or KATAKANA


class Column:
    """One vertical stream of characters."""

    __slots__ = ("head", "speed", "length", "active", "delay", "chars",
                 "prev_top", "prev_bot", "dirty")

    def __init__(self, rows, rng, cfg):
        self.chars = {}
        self.prev_top = 0
        self.prev_bot = -1
        self.dirty = None
        self.reset(rows, rng, cfg, initial=True)

    def reset(self, rows, rng, cfg, initial=False):
        self.head = rng.uniform(-rows, 0) if initial else -rng.uniform(0, 8)
        self.speed = rng.uniform(cfg.speed_min, cfg.speed_max)
        self.length = rng.randint(cfg.trail_min, cfg.trail_max)
        self.active = True
        self.delay = 0.0 if initial else rng.uniform(0.0, cfg.respawn)
        self.chars = {}


class RainArea:
    """Simulation + drawing for a single monitor-sized window."""

    def __init__(self, w, h, cfg):
        self.cfg = cfg
        self.rng = random.Random()
        self.charset = build_charset(cfg.mix)
        self.atlas = {}
        self._measure()
        self.resize(w, h)

    # -- glyph atlas ----------------------------------------------------
    def _measure(self):
        tmp = cairo.ImageSurface(cairo.FORMAT_ARGB32, 8, 8)
        cr = cairo.Context(tmp)
        cr.select_font_face(self.cfg.font, cairo.FONT_SLANT_NORMAL,
                            cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(self.cfg.size)
        fa = cr.font_extents()          # ascent, descent, height, max_x_adv, ...
        widths = [cr.text_extents(c).x_advance for c in self.charset[:80]]
        self.cell_w = max(1, int(round(max(widths))))
        self.cell_h = max(1, int(round(fa[2] * self.cfg.line_spacing)))
        self.baseline = int(round(fa[0]))

    def _levels(self):
        """Colour ramp: index 0 = head, then fading tail."""
        cfg = self.cfg
        hr, hg, hb = cfg.head_rgb
        tr, tg, tb = cfg.tail_rgb
        out = [(hr, hg, hb, 1.0)]
        n = cfg.levels - 1
        for i in range(n):
            t = i / max(1, n - 1)
            a = (1.0 - t) ** cfg.fade_gamma
            out.append((tr, tg, tb, max(0.0, a) * cfg.opacity))
        return out

    def _build_atlas(self):
        self.atlas.clear()
        levels = self._levels()
        for ch in set(self.charset):
            for li, (r, g, b, a) in enumerate(levels):
                if a <= 0.004:
                    continue
                surf = cairo.ImageSurface(cairo.FORMAT_ARGB32,
                                          self.cell_w, self.cell_h)
                cr = cairo.Context(surf)
                cr.select_font_face(self.cfg.font, cairo.FONT_SLANT_NORMAL,
                                    cairo.FONT_WEIGHT_BOLD)
                cr.set_font_size(self.cfg.size)
                cr.set_source_rgba(r, g, b, a)
                cr.move_to(0, self.baseline)
                cr.show_text(ch)
                surf.flush()
                self.atlas[(ch, li)] = surf
        self.n_levels = len(levels)

    # -- geometry -------------------------------------------------------
    def resize(self, w, h):
        self.w, self.h = w, h
        self.cols = max(1, w // self.cell_w)
        self.rows = max(1, h // self.cell_h) + 2
        self._build_atlas()
        n_active = max(1, int(self.cols * self.cfg.density))
        self.columns = [Column(self.rows, self.rng, self.cfg)
                        for _ in range(self.cols)]
        # Only a fraction of columns run at once.
        for i, col in enumerate(self.columns):
            if i >= n_active:
                col.active = False
                col.delay = self.rng.uniform(0.0, self.cfg.respawn * 2)

    # -- simulation -----------------------------------------------------
    def step(self, dt):
        rng = self.rng
        cfg = self.cfg
        rows = self.rows
        mutate = cfg.mutate * dt
        for col in self.columns:
            col.dirty = None
            if not col.active:
                if col.prev_bot >= col.prev_top:
                    # erase whatever this column drew on its final frame
                    col.dirty = (col.prev_top, col.prev_bot)
                    col.prev_bot = -1
                    col.prev_top = 0
                col.delay -= dt
                if col.delay <= 0:
                    col.reset(rows, rng, cfg)
                continue
            if col.delay > 0:
                col.delay -= dt
                continue
            prev = int(col.head)
            col.head += col.speed * dt
            now = int(col.head)
            for r in range(prev + 1, now + 1):
                col.chars[r] = rng.choice(self.charset)
            if col.chars and rng.random() < mutate:
                k = rng.choice(list(col.chars.keys()))
                col.chars[k] = rng.choice(self.charset)

            cur_top = now - col.length
            cur_bot = now
            if col.prev_bot >= col.prev_top:
                col.dirty = (min(col.prev_top, cur_top),
                             max(col.prev_bot, cur_bot))
            else:
                col.dirty = (cur_top, cur_bot)
            col.prev_top, col.prev_bot = cur_top, cur_bot

            if col.head - col.length > rows:
                col.active = False
                col.delay = rng.uniform(0.0, cfg.respawn)
                col.chars = {}

    # -- drawing --------------------------------------------------------
    def draw(self, cr):
        cfg = self.cfg
        if cfg.clear:
            # GTK may already hand us a cleared buffer; --no-clear skips this
            # full-surface write, which is the single biggest cost per frame.
            cr.set_operator(cairo.OPERATOR_SOURCE)
            cr.set_source_rgba(0.0, 0.0, 0.0, cfg.bg_alpha)
            cr.paint()
            cr.set_operator(cairo.OPERATOR_OVER)

        cx1, cy1, cx2, cy2 = cr.clip_extents()
        cw, ch = self.cell_w, self.cell_h
        nl = self.n_levels
        atlas = self.atlas
        for ci, col in enumerate(self.columns):
            if not col.active or col.delay > 0:
                continue
            x0 = ci * cw
            if x0 + cw <= cx1 or x0 >= cx2:
                continue
            head = int(col.head)
            x = ci * cw
            for i in range(col.length):
                r = head - i
                if r < 0:
                    continue
                if r * ch > self.h:
                    continue
                c = col.chars.get(r)
                if c is None:
                    continue
                li = 0 if i == 0 else 1 + int((i - 1) * (nl - 1) / col.length)
                if li >= nl:
                    continue
                surf = atlas.get((c, li))
                if surf is None:
                    continue
                cr.set_source_surface(surf, x, r * ch)
                cr.paint()


class RainWindow(Gtk.Window):
    def __init__(self, geom, cfg):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        x, y, w, h = geom
        self.cfg = cfg
        self.area = RainArea(w, h, cfg)

        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual is None:
            print("warning: no RGBA visual; window will not be transparent",
                  file=sys.stderr)
        else:
            self.set_visual(visual)

        self.set_app_paintable(True)
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_accept_focus(False)
        self.set_focus_on_map(False)
        self.set_keep_below(True)
        if cfg.window_type == "desktop":
            # A NORMAL window is kept above the desktop layer by Openbox no
            # matter what _NET_WM_STATE_BELOW says, so declare the real type.
            # Being transparent, the icons pcmanfm draws underneath show through.
            self.set_type_hint(Gdk.WindowTypeHint.DESKTOP)
        self.set_default_size(w, h)
        self.stick()
        self.connect("draw", self.on_draw)
        self.connect("destroy", Gtk.main_quit)

        self.realize()
        gw = self.get_window()
        gw.set_override_redirect(cfg.override_redirect)
        # click-through: empty input region
        try:
            gw.input_shape_combine_region(cairo.Region(), 0, 0)
        except Exception as e:
            print("input passthrough unavailable:", e, file=sys.stderr)

        self.move(x, y)
        self.resize(w, h)
        self.show_all()
        self.move(x, y)
        self.resize(w, h)
        # Openbox does not reliably honour _NET_WM_STATE_BELOW set before map,
        # so re-assert it after mapping and then periodically as insurance.
        GLib.timeout_add(300, self._sink)
        GLib.timeout_add_seconds(5, self._sink_forever)

    def _sink(self):
        gw = self.get_window()
        if self.cfg.window_type == "desktop":
            # within the desktop layer, sit above pcmanfm-qt's desktop window
            if gw is not None:
                gw.raise_()
        else:
            self.set_keep_below(True)
            if gw is not None:
                gw.lower()
        return False

    def _sink_forever(self):
        self._sink()
        return True

    def on_draw(self, _w, cr):
        self.area.draw(cr)
        return False

    def apply_damage(self):
        """Queue redraws only for the column strips that actually changed."""
        a = self.area
        cw, ch, H = a.cell_w, a.cell_h, a.h
        for ci, col in enumerate(a.columns):
            d = col.dirty
            if d is None:
                continue
            top, bot = d
            y0 = max(0, top * ch)
            y1 = min(H, (bot + 1) * ch)
            if y1 <= y0:
                continue
            self.queue_draw_area(ci * cw, int(y0), cw, int(y1 - y0))


def parse_args(argv):
    p = argparse.ArgumentParser(description="Flat 2D Phosphor rain wallpaper")
    p.add_argument("--geometry", action="append", default=[],
                   metavar="WxH+X+Y", help="repeatable; one window per entry")
    p.add_argument("--fps", type=float, default=14.0)
    p.add_argument("--size", type=float, default=16.0, help="font pixel size")
    p.add_argument("--font", default="Noto Sans Mono CJK JP")
    p.add_argument("--line-spacing", type=float, default=1.0)
    p.add_argument("--density", type=float, default=0.55,
                   help="fraction of columns streaming at once (0-1)")
    p.add_argument("--speed-min", type=float, default=6.0, help="rows/sec")
    p.add_argument("--speed-max", type=float, default=20.0, help="rows/sec")
    p.add_argument("--trail-min", type=int, default=8)
    p.add_argument("--trail-max", type=int, default=28)
    p.add_argument("--respawn", type=float, default=3.0, help="max idle seconds")
    p.add_argument("--mutate", type=float, default=6.0, help="glyph changes/sec")
    p.add_argument("--levels", type=int, default=14, help="brightness steps")
    p.add_argument("--fade-gamma", type=float, default=1.6)
    p.add_argument("--opacity", type=float, default=0.95)
    p.add_argument("--bg-alpha", type=float, default=0.0,
                   help="0 = fully transparent, 1 = solid black backdrop")
    p.add_argument("--mix", default="katakana,digits,latin")
    p.add_argument("--window-type", default="desktop",
                   choices=["desktop", "normal"],
                   help="desktop: structurally in the desktop layer (default)")
    p.add_argument("--no-clear", dest="clear", action="store_false",
                   help="skip the explicit full-surface clear each frame")
    p.add_argument("--override-redirect", action="store_true",
                   help="bypass the window manager entirely")
    cfg = p.parse_args(argv)
    cfg.head_rgb = (0.80, 1.0, 0.85)
    cfg.tail_rgb = (0.10, 1.0, 0.26)
    cfg.mix = [s.strip() for s in cfg.mix.split(",") if s.strip()]
    return cfg


def main():
    cfg = parse_args(sys.argv[1:])
    geoms = []
    for g in cfg.geometry:
        try:
            wh, x, y = g.replace("+", " +").split()
            w, h = wh.split("x")
            geoms.append((int(x), int(y), int(w), int(h)))
        except Exception:
            print(f"bad --geometry {g!r}, want WxH+X+Y", file=sys.stderr)
            return 2
    if not geoms:
        print("no --geometry given", file=sys.stderr)
        return 2

    wins = [RainWindow(g, cfg) for g in geoms]
    interval = max(10, int(1000.0 / cfg.fps))
    dt = interval / 1000.0

    def tick():
        for wdw in wins:
            wdw.area.step(dt)
            wdw.queue_draw()   # one big damage rect beats many small ones here
        return True

    GLib.timeout_add(interval, tick)
    Gtk.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())

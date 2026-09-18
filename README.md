# phosphor-desktop

A green-phosphor theme for **Lubuntu / LXQt + Openbox on X11**, with a genuine
animated desktop background: falling katakana, latin and digit glyphs, drawn
behind your windows and *underneath* your desktop icons.

![Digital rain](screenshots/rain.png)

It also ships outline folder icons, and matching panel, window, menu and
terminal themes.

---

## Install

```bash
git clone https://github.com/tzarz/phosphor-desktop.git
cd phosphor-desktop
./install.sh
```

Everything lands in your home directory. **No root.** Before changing any
setting the installer copies the original into
`~/.phosphor-desktop-backup-<timestamp>/`, and `./uninstall.sh` puts it all back.

Dependencies (the installer checks these and tells you if any are missing):

```bash
sudo apt install python3-gi gir1.2-gtk-3.0 python3-cairo papirus-icon-theme \
                 lxqt-themes fonts-noto-cjk xscreensaver-gl x11-xserver-utils
```

Then:

```bash
phosphor-rain start        # also: stop, restart, toggle, status
```

It starts automatically at login.

| | |
|---|---|
| ![Desktop](screenshots/desktop.png) | ![Folders](screenshots/folders.png) |
| ![Terminal](screenshots/terminal.png) | ![Panel](screenshots/panel.png) |

---

## How an animated background actually works on X11

This is the interesting part, and most of the tutorials you will find online get
it wrong. Here is what is really going on.

### Why you cannot just draw on the root window

The traditional advice is to draw on the **root window** — the bottom-most X
window that everything else stacks on top of:

```bash
/usr/libexec/xscreensaver/glmatrix -root      # looks right, does nothing
```

On a bare window manager that works. On LXQt it does not, and you will see
nothing at all. Run this and you will see why:

```bash
xwininfo -root -tree | grep desktop
#   "pcmanfm-desktop-1": ("pcmanfm-qt" "pcmanfm-qt")  9200x2160+0+0
```

The file manager, `pcmanfm-qt --desktop`, owns a window covering your **entire**
screen area. That is what paints your wallpaper and draws your desktop icons.
Anything you render on the root window is hidden behind it. The same is true on
GNOME (Nautilus) and XFCE (xfdesktop).

So a live background cannot be a root-window drawing. It has to be a window.

### Window types, not window stacking

The obvious next idea is a normal window pushed to the bottom:

```bash
wmctrl -r <window> -b add,below      # not enough
xdotool windowlower <window>         # also not enough
```

Neither works, and it is worth understanding why. Window managers sort windows
into **layers** before they sort within a layer. Openbox's order, bottom to top:

```
desktop layer   <- _NET_WM_WINDOW_TYPE_DESKTOP
below layer     <- _NET_WM_STATE_BELOW
normal layer
above layer     <- _NET_WM_STATE_ABOVE
dock layer      <- panels
```

`_NET_WM_STATE_BELOW` only moves you to the bottom of the *managed* layers. It
is still above the desktop layer, so your animation covers the file manager's
window and your icons vanish. No amount of lowering fixes that, because lowering
operates *within* a layer.

The fix is to declare what the window actually is:

```python
win.set_type_hint(Gdk.WindowTypeHint.DESKTOP)   # _NET_WM_WINDOW_TYPE_DESKTOP
```

This is a standard [EWMH](https://specifications.freedesktop.org/wm-spec/latest/)
property meaning *"this window is the desktop background."* Every compliant
window manager honours it. It is the same mechanism the file managers above use,
and the same one `xwinwrap` uses. Declaring it puts the animation structurally
in the desktop layer — permanently below every application, with no fighting.

Then raise it *within* that layer so it sits above the file manager's window:

```python
self.get_window().raise_()
```

### Keeping your icons and your clicks

Being above the file manager's window would normally hide your desktop icons.
Two X11 features prevent that.

**Per-pixel transparency.** Ask for an RGBA visual and clear to alpha 0 each
frame. The icons underneath show through the gaps between glyphs:

```python
win.set_visual(win.get_screen().get_rgba_visual())
win.set_app_paintable(True)
# in the draw handler:
cr.set_operator(cairo.OPERATOR_SOURCE)
cr.set_source_rgba(0, 0, 0, 0)
cr.paint()
```

This needs a compositor running. picom ships with Lubuntu and is on by default.

**An empty input shape.** Otherwise your window swallows every click on the
desktop:

```python
win.get_window().input_shape_combine_region(cairo.Region(), 0, 0)
```

An empty region means "no part of me accepts input", so clicks pass straight
through to the icons behind.

Those three things — desktop window type, RGBA transparency, empty input
shape — are the whole trick. Everything else is drawing.

### Drawing glyphs cheaply

Rendering text every frame is slow, because each glyph has to be shaped and
rasterised. Instead, rasterise every glyph once at every brightness level into a
small image, then just copy the images:

```python
for ch in charset:
    for level, (r, g, b, a) in enumerate(brightness_ramp):
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, cell_w, cell_h)
        cr = cairo.Context(surf)
        cr.set_source_rgba(r, g, b, a)
        cr.show_text(ch)
        atlas[(ch, level)] = surf
```

Per frame it is just `set_source_surface` + `paint`, which is a blit. No text
shaping, and no GPU work at all — the compositor was already compositing your
windows anyway.

---

## What it costs, and what actually costs it

Measured with `/proc/<pid>/stat` deltas over 20s, driving a 3440x1440 plus a
1920x1080 output on a 32-core machine.

| Setup | % of one core | % of machine |
|---|---|---|
| 3D OpenGL screensaver as wallpaper | ~5% x2 procs | **+20–25pp GPU** |
| this renderer, 14 fps | 13.60% | 0.425% |
| this renderer, 10 fps | 9.30% | 0.291% |
| **this renderer, 3 fps (default)** | **2.35%** | **0.073%** |

**The glyphs are free.** At density 0.02 — almost nothing on screen — it cost
6.73%. At density 0.60 it cost 6.45%. Identical within noise. The entire cost is
the per-frame clear of a large ARGB surface.

That is a useful thing to know: turn density, trail length and speed up as far
as you like, they are not what you are paying for. Only **frame rate** and
**total window area** matter. Want it cheaper? Lower `--fps`, or skip a monitor.

### Two optimisations that made it worse

Written down so you do not repeat them:

- **Damage-limited redraw.** Calling `queue_draw_area` per changed column
  instead of `queue_draw` for the whole window went from 9.30% to **15.53%**.
  Many small damage rectangles cost more in clip handling and compositing than
  one big one.
- **Skipping the explicit clear.** Saved 0.3%, because GTK clears the double
  buffer anyway. The `--no-clear` flag exists and is not worth using.

---

## Configuring it

`~/.config/phosphor-rain.conf`:

```sh
EXCLUDE=""                 # xrandr outputs that must never show the wallpaper
RAIN_OPTS="--fps 3 --size 18 --density 0.60 --trail-min 4 --trail-max 56 \
           --speed-min 0.625 --speed-max 2.0 --mutate 0.8 --bg-alpha 0.0"
```

Worth knowing: `--mix katakana,digits,latin,symbols` picks the character set,
`--bg-alpha` goes from 0 (fully transparent) to 1 (solid black backdrop),
`--font` takes any font name, and `--window-type normal` opts out of the desktop
window type if you want to see the difference for yourself.

**`EXCLUDE`** is a space-separated list of `xrandr` output names to skip. Use it
when a display is not a desktop — a capture card, a projector, or a scientific
instrument that must show only its own output:

```sh
EXCLUDE="HDMI-1 DP-3"
```

---

## The rest of the theme

**Folder icons** are drawn from scratch as SVG line art in
`src/icons/folder_svg.py` — a near-black body, a green outline, a faint glow,
and a glyph per folder type. `src/icons/build_icons.py` generates them for every
size and adds them to a theme that inherits Papirus-Dark, then recolours the
monochrome action/status/panel icons by mapping each grey to a green of the same
luminance. Application and mimetype icons are deliberately left alone, so your
apps stay recognisable.

One trap worth knowing if you build your own icon theme: file managers ask for
the icon name **`inode-directory`**, not `folder`. Override only `folder` and
your theme will silently fall through to the one it inherits from.

**LXQt and Openbox themes** are generated at install time from the stock `dark`
and `Nightmare` themes on your machine, rather than vendored, so they track
their upstreams and the repo stays small.

**The terminal scheme** is mostly green, but keeps red and amber readable so
error output, diffs and `ls` colours still work. A fully monochrome palette
photographs well and is miserable to use.

---

## What goes where

| Path | What |
|---|---|
| `~/.local/share/phosphor-rain/rain.py` | the renderer |
| `~/.local/bin/phosphor-rain` | control script |
| `~/.config/phosphor-rain.conf` | tuning |
| `~/.local/share/icons/Papirus-Phosphor/` | icon theme |
| `~/.local/share/lxqt/themes/Phosphor/` | LXQt theme |
| `~/.themes/Phosphor/` | Openbox theme |
| `~/.local/share/qterminal/color-schemes/` | terminal scheme |
| `~/.config/autostart/` | autostart entries |

Settings edited: `lxqt.conf` (theme, icon theme), `openbox/rc.xml` (theme plus a
window rule), `pcmanfm-qt/lxqt/settings.conf` (desktop colours and font).

---

## Gotchas

- **X11 only.** Per-pixel-transparent desktop windows and input shapes do not
  port to Wayland as they stand.
- **A compositor is required** for the transparency.
- **`pcmanfm-qt` and `qterminal` rewrite their config files when they exit.**
  Edit their settings while they are running and your changes are silently
  overwritten on quit. Stop them first. The installer does; you should too.
- Other desktops get the wallpaper and icon theme, but not the LXQt/Openbox
  themes.

## If you got here searching for something

This is a green-on-black **digital rain** desktop: the falling-glyph screen
effect popularised by *The Matrix* (1999), with folder icons in the neon
outline style of *Tron* (1982). Those films describe the **look** and nothing
more — this project is not affiliated with or endorsed by them, contains no
assets from them, and borrows no names. Every glyph, icon, colour and line of
code here was made for this repository.

Things people search for that land here: matrix digital rain wallpaper linux ·
animated wallpaper X11 · live wallpaper LXQt · cmatrix as a desktop background ·
falling katakana background · tron style folder icons · neon outline icon theme ·
green phosphor terminal theme · CRT desktop theme · cyberpunk linux rice ·
hacker desktop setup · Lubuntu ricing · Openbox live wallpaper ·
`_NET_WM_WINDOW_TYPE_DESKTOP` example · transparent click-through X11 window

## License

MIT

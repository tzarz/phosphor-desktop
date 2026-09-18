#!/usr/bin/env bash
#
# matrix-desktop installer for Lubuntu / LXQt + Openbox on X11.
#
# Everything installs into your home directory. Nothing needs root, and every
# file this touches is backed up first.
#
#   ./install.sh                      install + apply
#   ./install.sh --no-apply           install files, change no settings
#   ./install.sh --exclude "HDMI-0"   never draw the wallpaper on that output
#
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$HERE/src"
APPLY=1
EXCLUDE=""
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="$HOME/.matrix-desktop-backup-$STAMP"

while [ $# -gt 0 ]; do
    case "$1" in
        --no-apply) APPLY=0; shift ;;
        --exclude)  EXCLUDE="${2:-}"; shift 2 ;;
        -h|--help)  sed -n '2,12p' "$0"; exit 0 ;;
        *) echo "unknown option: $1" >&2; exit 2 ;;
    esac
done

say()  { printf '\033[38;5;46m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[38;5;214m[!]\033[0m %s\n' "$*"; }
die()  { printf '\033[38;5;196m[x]\033[0m %s\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------- dependencies
say "checking dependencies"
MISSING=()
need_file() { [ -e "$1" ] || MISSING+=("$2"); }
command -v python3 >/dev/null || MISSING+=("python3")
/usr/bin/python3 -c 'import gi; gi.require_version("Gtk","3.0"); from gi.repository import Gtk' \
    2>/dev/null || MISSING+=("python3-gi + gir1.2-gtk-3.0")
/usr/bin/python3 -c 'import cairo' 2>/dev/null || MISSING+=("python3-cairo")
need_file /usr/share/icons/Papirus-Dark "papirus-icon-theme"
need_file /usr/share/lxqt/themes/dark "lxqt-themes"
command -v xrandr >/dev/null || MISSING+=("x11-xserver-utils")
fc-list :lang=ja >/dev/null 2>&1 && [ -n "$(fc-list :lang=ja family)" ] \
    || MISSING+=("fonts-noto-cjk")
[ -x /usr/libexec/xscreensaver/glmatrix ] || [ -x /usr/lib/xscreensaver/glmatrix ] \
    || warn "xscreensaver-gl not found - the GLMatrix screensaver will be skipped"

if [ ${#MISSING[@]} -gt 0 ]; then
    echo
    die "missing dependencies: ${MISSING[*]}
    install them with:
      sudo apt install python3-gi gir1.2-gtk-3.0 python3-cairo papirus-icon-theme \\
                       lxqt-themes fonts-noto-cjk xscreensaver-gl x11-xserver-utils"
fi
say "all dependencies present"

backup() {
    [ -e "$1" ] || return 0
    mkdir -p "$BACKUP$(dirname "${1#$HOME}")"
    cp -a "$1" "$BACKUP${1#$HOME}"
}

# ------------------------------------------------------------------- live wallpaper
say "installing the live wallpaper"
mkdir -p "$HOME/.local/share/matrix-rain" "$HOME/.local/bin"
install -m 0644 "$SRC/rain/rain.py"      "$HOME/.local/share/matrix-rain/rain.py"
install -m 0755 "$SRC/rain/matrix-rain"  "$HOME/.local/bin/matrix-rain"
if [ ! -e "$HOME/.config/matrix-rain.conf" ]; then
    install -m 0644 "$SRC/rain/matrix-rain.conf" "$HOME/.config/matrix-rain.conf"
else
    say "keeping your existing ~/.config/matrix-rain.conf"
fi
if [ -n "$EXCLUDE" ]; then
    backup "$HOME/.config/matrix-rain.conf"
    sed -i "s|^EXCLUDE=.*|EXCLUDE=\"$EXCLUDE\"|" "$HOME/.config/matrix-rain.conf"
    say "excluded outputs: $EXCLUDE"
fi

# ------------------------------------------------------------------------ themes
say "building the LXQt theme"
/usr/bin/python3 "$SRC/lxqt/build_lxqt_theme.py" >/dev/null || die "LXQt theme build failed"

say "installing the Openbox theme"
mkdir -p "$HOME/.themes"
cp -a "$SRC/openbox/Matrix" "$HOME/.themes/"

say "building the icon theme (this takes a moment)"
/usr/bin/python3 "$SRC/icons/build_icons.py" || die "icon theme build failed"
command -v gtk-update-icon-cache >/dev/null && \
    gtk-update-icon-cache -f -t "$HOME/.local/share/icons/Papirus-Matrix" >/dev/null 2>&1

# ---------------------------------------------------------------------- terminal
if [ -d /usr/share/qtermwidget6 ] || [ -d /usr/share/qtermwidget5 ] \
   || command -v qterminal >/dev/null; then
    # qtermwidget itself only reads /usr/share/qtermwidget*/color-schemes, but
    # qterminal additionally reads this user-writable directory. Verified by
    # testing each candidate path against a live qterminal.
    SCHEMES="$HOME/.local/share/qterminal/color-schemes"
    mkdir -p "$SCHEMES"
    install -m 0644 "$SRC/terminal/Matrix.colorscheme" "$SCHEMES/Matrix.colorscheme"
    say "installed QTerminal colour scheme to $SCHEMES"

    QTI="$HOME/.config/qterminal.org/qterminal.ini"
    if pgrep -x qterminal >/dev/null 2>&1; then
        warn "qterminal is running and rewrites its config on exit."
        warn "Pick it yourself: Preferences > Appearance > Color scheme > Matrix"
    elif [ -f "$QTI" ]; then
        backup "$QTI"
        /usr/bin/python3 - "$QTI" <<'PYQT'
import sys, re, pathlib
p = pathlib.Path(sys.argv[1]); s = p.read_text()
for k, v in (("colorScheme", "Matrix"), ("fontFamily", "Ubuntu Mono")):
    if re.search(rf"(?m)^{k}=", s):
        s = re.sub(rf"(?m)^{k}=.*$", f"{k}={v}", s)
p.write_text(s)
PYQT
        say "set QTerminal colour scheme to Matrix"
    fi
fi

# -------------------------------------------------------------------- screensaver
if [ -x /usr/libexec/xscreensaver/glmatrix ] || [ -x /usr/lib/xscreensaver/glmatrix ]; then
    if [ ! -e "$HOME/.xscreensaver" ]; then
        install -m 0644 "$SRC/xscreensaver/xscreensaver.conf" "$HOME/.xscreensaver"
        say "installed GLMatrix screensaver config"
    else
        say "keeping your existing ~/.xscreensaver"
    fi
fi

# ---------------------------------------------------------------------- autostart
say "installing autostart entries"
mkdir -p "$HOME/.config/autostart"
for f in "$SRC"/autostart/*.desktop; do
    b="$(basename "$f")"
    backup "$HOME/.config/autostart/$b"
    sed "s|__HOME__|$HOME|g" "$f" > "$HOME/.config/autostart/$b"
done

if [ "$APPLY" -eq 0 ]; then
    say "files installed; settings left untouched (--no-apply)"
    echo "   run 'matrix-rain start' to try the wallpaper"
    exit 0
fi

# ------------------------------------------------------------------------- apply
say "applying settings (backup: $BACKUP)"

backup "$HOME/.config/lxqt/lxqt.conf"
/usr/bin/python3 - <<'PY'
import pathlib, re
p = pathlib.Path.home()/".config/lxqt/lxqt.conf"
p.parent.mkdir(parents=True, exist_ok=True)
t = p.read_text() if p.exists() else "[General]\n"
def setkey(t,k,v):
    if re.search(rf"(?m)^{k}=", t): return re.sub(rf"(?m)^{k}=.*$", f"{k}={v}", t)
    return re.sub(r"(?m)^\[General\]$", f"[General]\n{k}={v}", t, count=1)
for k,v in (("theme","Matrix"),("icon_theme","Papirus-Matrix")):
    t = setkey(t,k,v)
p.write_text(t)
PY

backup "$HOME/.config/openbox/rc.xml"
/usr/bin/python3 - <<'PY'
import pathlib, re
p = pathlib.Path.home()/".config/openbox/rc.xml"
if p.exists():
    t = p.read_text()
    t = re.sub(r"(<theme>.*?<name>)[^<]*(</name>)", r"\1Matrix\2", t, count=1, flags=re.S)
    rule = """    <!-- matrix-desktop live wallpaper -->
    <application name="rain.py" class="Rain.py">
      <decor>no</decor>
      <skip_taskbar>yes</skip_taskbar>
      <skip_pager>yes</skip_pager>
      <desktop>all</desktop>
      <focus>no</focus>
      <maximized>no</maximized>
    </application>
"""
    if 'name="rain.py"' not in t:
        t = t.replace("  </applications>", rule + "  </applications>", 1)
    p.write_text(t)
PY

# pcmanfm-qt rewrites its config on exit, so it must be stopped BEFORE editing.
DESKTOP_WAS_RUNNING=0
for p in $(pgrep -x pcmanfm-qt 2>/dev/null); do
    if tr '\0' ' ' < "/proc/$p/cmdline" 2>/dev/null | grep -q -- '--desktop'; then
        DESKTOP_WAS_RUNNING=1; kill "$p"
    fi
done
[ "$DESKTOP_WAS_RUNNING" -eq 1 ] && sleep 2

PCM="$HOME/.config/pcmanfm-qt/lxqt/settings.conf"
if [ -f "$PCM" ]; then
    backup "$PCM"
    /usr/bin/python3 - "$PCM" <<'PY'
import sys, re, pathlib
p = pathlib.Path(sys.argv[1]); s = p.read_text()
for k, v in (("BgColor", "#000000"), ("FgColor", "#19FF42"),
             ("ShadowColor", "#001A05"), ("WallpaperMode", "none"),
             ("Font", '"Ubuntu Mono,12,-1,5,700,0,0,0,0,0,0,0,0,0,0,1,Bold"')):
    s = re.sub(rf'(?m)^{k}=.*$', f'{k}={v}', s) if re.search(rf'(?m)^{k}=', s) \
        else re.sub(r'(?m)^\[Desktop\]$', f'[Desktop]\n{k}={v}', s, count=1)
p.write_text(s)
PY
fi

command -v openbox >/dev/null && openbox --reconfigure 2>/dev/null
if [ "$DESKTOP_WAS_RUNNING" -eq 1 ]; then
    setsid nohup pcmanfm-qt --desktop --profile=lxqt >/dev/null 2>&1 < /dev/null &
fi
if pgrep -x lxqt-panel >/dev/null; then
    pkill -x lxqt-panel; sleep 2
    setsid nohup lxqt-panel >/dev/null 2>&1 < /dev/null &
fi

"$HOME/.local/bin/matrix-rain" restart >/dev/null 2>&1

echo
say "done. backup of everything changed: $BACKUP"
echo "   matrix-rain {start|stop|toggle|status}   control the wallpaper"
echo "   ~/.config/matrix-rain.conf               fps, density, excluded outputs"
echo "   ./uninstall.sh                           revert"

#!/usr/bin/env bash
#
# Remove phosphor-desktop and restore the most recent backup taken by install.sh.
#
#   ./uninstall.sh                 restore newest backup
#   ./uninstall.sh --keep-config   remove the theme files, leave settings alone
#
set -uo pipefail

KEEP=0
[ "${1:-}" = "--keep-config" ] && KEEP=1

say() { printf '\033[38;5;46m==>\033[0m %s\n' "$*"; }

say "stopping the live wallpaper"
[ -x "$HOME/.local/bin/phosphor-rain" ] && "$HOME/.local/bin/phosphor-rain" stop >/dev/null 2>&1

say "removing installed files"
rm -rf "$HOME/.local/share/phosphor-rain" \
       "$HOME/.local/share/lxqt/themes/Phosphor" \
       "$HOME/.local/share/icons/Papirus-Phosphor" \
       "$HOME/.themes/Phosphor"
rm -f  "$HOME/.local/share/qterminal/color-schemes/Phosphor.colorscheme" \
       "$HOME/.local/share/lxqt/palettes/Phosphor" \
       "$HOME/.local/bin/phosphor-rain" \
       "$HOME/.config/autostart/phosphor-rain.desktop" \
       "$HOME/.config/autostart/xscreensaver-rain.desktop"

if [ "$KEEP" -eq 1 ]; then
    say "left your settings untouched (--keep-config)"
    exit 0
fi

BACKUP=$(ls -1d "$HOME"/.phosphor-desktop-backup-* 2>/dev/null | sort | tail -1)
if [ -z "$BACKUP" ]; then
    say "no backup found; settings left as they are"
    echo "   set the theme and icons back by hand in LXQt Settings > Appearance"
    exit 0
fi

say "restoring from $BACKUP"
# pcmanfm-qt rewrites its config on exit: stop it before restoring.
RESTART=0
for p in $(pgrep -x pcmanfm-qt 2>/dev/null); do
    if tr '\0' ' ' < "/proc/$p/cmdline" 2>/dev/null | grep -q -- '--desktop'; then
        RESTART=1; kill "$p"
    fi
done
[ "$RESTART" -eq 1 ] && sleep 2

( cd "$BACKUP" && find . -type f -print0 | while IFS= read -r -d '' f; do
    dest="$HOME/${f#./}"
    mkdir -p "$(dirname "$dest")"
    cp -a "$f" "$dest"
    echo "   restored ${f#./}"
done )

command -v openbox >/dev/null && openbox --reconfigure 2>/dev/null
[ "$RESTART" -eq 1 ] && setsid nohup pcmanfm-qt --desktop --profile=lxqt >/dev/null 2>&1 < /dev/null &
if pgrep -x lxqt-panel >/dev/null; then
    pkill -x lxqt-panel; sleep 2
    setsid nohup lxqt-panel >/dev/null 2>&1 < /dev/null &
fi

say "done"

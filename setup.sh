#!/usr/bin/env bash
# ============================================================================
#  ABYSS ECONOMY :: AUTO-SETUP
#  One-command installer. Detects the host distribution, installs every
#  system dependency, builds an isolated Python environment and verifies
#  the game package before the first launch.
#
#  Usage:
#      ./setup.sh              install, verify, then launch the game
#      ./setup.sh --no-run     install and verify only (CI / headless)
#      ./setup.sh --uninstall  remove .venv and generated caches
#      ./setup.sh --help       usage information
#
#  Tested targets: Debian/Ubuntu, Arch, Fedora/RHEL, openSUSE, other glibc
#  Linux, macOS. Windows users: see docs/install/WINDOWS.md
#  License: proprietary. See LICENSE. Copyright (c) 2026.
# ============================================================================

set -u
umask 022

VERSION="1.0.0"
PYTHON_MIN_MINOR=8
VENV_DIR=".venv"
GAME_MODULE="game.engine.app"
PIP_MIRROR="${PIP_MIRROR:-}"          # optional: export PIP_MIRROR=https://...

RUN_GAME=1
UNINSTALL=0
for arg in "$@"; do
    case "$arg" in
        --no-run)    RUN_GAME=0 ;;
        --uninstall) UNINSTALL=1 ;;
        -h|--help)
            sed -n '2,17p' "$0" | sed 's/^# \{0,2\}//'
            exit 0 ;;
        *)
            echo "unknown option: $arg (try --help)" >&2
            exit 2 ;;
    esac
done

# ---------------------------------------------------------------------------
#  Palette and drawing primitives (ANSI, auto-disabled when not a tty)
# ---------------------------------------------------------------------------
if [ -t 1 ] && [ "${TERM:-dumb}" != "dumb" ] && [ "${NO_COLOR:-}" = "" ]; then
    C_RESET=$'\033[0m';   C_BOLD=$'\033[1m';   C_DIM=$'\033[2m'
    C_RED=$'\033[31m';    C_GREEN=$'\033[32m'; C_YELLOW=$'\033[33m'
    C_BLUE=$'\033[34m';   C_MAGENTA=$'\033[35m'; C_CYAN=$'\033[36m'
    C_HGREEN=$'\033[92m'; C_HCYAN=$'\033[96m'; C_HYELLOW=$'\033[93m'
else
    C_RESET=""; C_BOLD=""; C_DIM=""; C_RED=""; C_GREEN=""
    C_YELLOW=""; C_BLUE=""; C_MAGENTA=""; C_CYAN=""
    C_HGREEN=""; C_HCYAN=""; C_HYELLOW=""
fi

hr() {
    local w=62 line=""
    while [ "${#line}" -lt "$w" ]; do line="${line}-"; done
    printf '%s%s%s\n' "$C_DIM" "${line:0:$w}" "$C_RESET"
}

say()  { printf '   %s\n' "$*"; }
ok()   { printf '  [%sOK%s]   %s\n' "$C_HGREEN" "$C_RESET" "$*"; }
info() { printf '  [%s..%s]   %s\n' "$C_CYAN" "$C_RESET" "$*"; }
warn() { printf '  [%s!!%s]   %s\n' "$C_HYELLOW" "$C_RESET" "$*"; }
err()  { printf '  [%sXX%s]   %s\n' "$C_RED" "$C_RESET" "$*" >&2; }

step_no=0
step() {
    step_no=$((step_no + 1))
    printf '\n'
    hr
    printf '%s[%02d]%s %s%s%s\n' "$C_HCYAN" "$step_no" "$C_RESET" "$C_BOLD" "$*" "$C_RESET"
    hr
}

banner() {
    clear 2>/dev/null || true
    cat <<EOF
${C_HCYAN}
  ▄▀▄ ▄▀▀ ▄▀▄ ▄▀▀▄ ▄▀▄   ▄▀▀ ▀▀▄ ▄▀▄ ▄▀▀▄ █▀▄ █▀▀ █▄▀ █▄▄ █
  █▀█ ▀▀▄ █▀█ ▀▀▄▀ █▀█   ▀▀▄ █▀█ █▀█ ▀▀▄▀ █▀▄ ██▄ █▀█ █▄█ ▌
  ▀   ▀▀▀ ▀   ▀  ▀ ▀     ▀▀▀ ▀▀▘ ▀   ▀  ▀ ▀  ▀ ▀▀▘ ▀ ▀ ▀▀▀ ▀
${C_RESET}${C_DIM}  economy-driven roguelike :: automated source setup v${VERSION}${C_RESET}
EOF
}

fail_trap() {
    err "installation aborted at line $1"
    say "fix the problem above, then re-run:  ./setup.sh"
    exit 1
}
trap 'fail_trap $LINENO' ERR

# ---------------------------------------------------------------------------
#  Privilege helper
# ---------------------------------------------------------------------------
if [ "$(id -u)" -eq 0 ]; then
    SUDO=""
elif command -v sudo >/dev/null 2>&1; then
    SUDO="sudo"
else
    SUDO=""
    warn "not root and sudo unavailable - system packages may fail to install"
fi

run_root() {
    if [ "$SUDO" = "sudo" ]; then
        info "administrator privileges required - you may be prompted for a password"
    fi
    $SUDO "$@"
}

pkg_install() {
    case "$PKG_FAMILY" in
        apt)        DEBIAN_FRONTEND=noninteractive run_root apt-get install -y "$@" ;;
        pacman)     run_root pacman -S --noconfirm --needed "$@" ;;
        dnf|yum)    run_root "$PKG_TOOL" install -y "$@" ;;
        zypper)     run_root zypper --non-interactive install "$@" ;;
        brew)       brew install "$@" ;;
        none|*)     return 0 ;;
    esac
}

# ---------------------------------------------------------------------------
#  System detection
# ---------------------------------------------------------------------------
detect_system() {
    OS_KIND="$(uname -s | tr '[:upper:]' '[:lower:]')"
    DIST_ID="unknown"; DIST_LABEL="Unknown"; PKG_FAMILY="none"; PKG_TOOL=""

    if [ "$OS_KIND" = "darwin" ]; then
        DIST_ID="macos"; DIST_LABEL="macOS $(sw_vers -productVersion 2>/dev/null)"
        PKG_FAMILY="brew"; PKG_TOOL="brew"
        return 0
    fi

    if [ -r /etc/os-release ]; then
        # shellcheck disable=SC1091
        . /etc/os-release
        DIST_ID="${ID:-unknown}"
        DIST_LABEL="${PRETTY_NAME:-$DIST_ID}"
        LIKE="${ID_LIKE:-}"
        case " $DIST_ID $LIKE " in
            *debian*|*ubuntu*|*mint*)                      PKG_FAMILY="apt" ;;
            *arch*|*manjaro*|*endeavour*|*cachyos*|*garuda*) PKG_FAMILY="pacman" ;;
            *fedora*|*rhel*|*centos*|*rocky*|*alma*|*amzn*)  PKG_FAMILY="dnf" ;;
            *suse*|*sles*|*opensuse*)                       PKG_FAMILY="zypper" ;;
        esac
    else
        if command -v apt-get  >/dev/null 2>&1; then PKG_FAMILY="apt"
        elif command -v pacman >/dev/null 2>&1; then PKG_FAMILY="pacman"
        elif command -v dnf    >/dev/null 2>&1; then PKG_FAMILY="dnf"
        elif command -v yum    >/dev/null 2>&1; then PKG_FAMILY="yum"
        elif command -v zypper >/dev/null 2>&1; then PKG_FAMILY="zypper"
        fi
    fi

    case "$PKG_FAMILY" in
        apt)    PKG_TOOL="apt-get" ;;
        pacman) PKG_TOOL="pacman" ;;
        dnf|yum)
            if command -v dnf >/dev/null 2>&1; then PKG_FAMILY="dnf"; PKG_TOOL="dnf"
            elif command -v yum >/dev/null 2>&1; then PKG_FAMILY="yum"; PKG_TOOL="yum"
            else PKG_FAMILY="none"; PKG_TOOL=""
            fi ;;
        zypper) PKG_TOOL="zypper" ;;
        none)   PKG_TOOL="" ;;
    esac
}

usage_footer() {
    printf '\n%sInstallation guide for this system:%s\n' "$C_BOLD" "$C_RESET"
    case "$DIST_ID" in
        arch|manjaro|endeavouros|cachyos|garuda) say "docs/install/ARCH-LINUX.md" ;;
        debian|ubuntu|linuxmint|pop)             say "docs/install/DEBIAN-UBUNTU.md" ;;
        fedora|rhel|centos|rocky|almalinux)      say "docs/install/FEDORA-RHEL.md" ;;
        *suse*)                                  say "docs/install/OPENSUSE.md" ;;
        macos)                                   say "docs/install/MACOS.md" ;;
        *)                                       say "docs/install/README.md" ;;
    esac
    say "docs/install/WINDOWS.md  (Windows, manual install)"
}

# ---------------------------------------------------------------------------
#  Uninstall mode
# ---------------------------------------------------------------------------
do_uninstall() {
    banner
    step "Uninstall: removing local build artifacts"
    rm -rf "$VENV_DIR" __pycache__ .pytest_cache
    find . -maxdepth 4 -type d -name "__pycache__" -prune -exec rm -rf {} + 2>/dev/null || true
    ok "virtual environment and caches removed"
    say "source files were left untouched; game data saves live in ~/.abyss_economy_save.json"
    exit 0
}
[ "$UNINSTALL" -eq 1 ] && do_uninstall

# ---------------------------------------------------------------------------
#  Prologue
# ---------------------------------------------------------------------------
banner
printf '  %sgood evening, traveller.%s  the forge will prepare itself.\n' "$C_DIM" "$C_RESET"

step "System fingerprint"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || { err "cannot enter script directory"; exit 1; }
detect_system
HOSTNAME_SAFE="$(hostname 2>/dev/null || echo 'unnamed-host')"
CPU_N="$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo '?')"
MEM_KB="$(grep MemTotal /proc/meminfo 2>/dev/null | awk '{print $2}' || echo '')"
[ -z "$MEM_KB" ] && [ "$OS_KIND" = "darwin" ] && MEM_KB="$(( $(sysctl -n hw.memsize 2>/dev/null || echo 0) / 1024 ))"
MEM_GB="?"
[ -n "$MEM_KB" ] && MEM_GB="$(( MEM_KB / 1048576 ))"

say "host        : ${C_BOLD}${HOSTNAME_SAFE}${C_RESET}   (${OS_KIND})"
say "system      : ${C_BOLD}${DIST_LABEL}${C_RESET}"
say "pkg family  : ${C_BOLD}${PKG_FAMILY}${C_RESET}   tool: ${PKG_TOOL:-n/a}"
say "cpu cores   : ${CPU_N}      memory: ${MEM_GB} GiB"
say "workdir     : ${SCRIPT_DIR}"
if [ "$PKG_FAMILY" = "none" ] && [ "$OS_KIND" != "windows" ]; then
    warn "package manager not recognised - system packages will be skipped"
fi

# ---------------------------------------------------------------------------
#  System dependencies
# ---------------------------------------------------------------------------
step "System dependencies"
case "$PKG_FAMILY" in
    apt)
        info "updating APT index"
        run_root apt-get update -qq
        pkg_install python3 python3-venv python3-pip python3-dev \
                    libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev \
                    gcc g++ make pkg-config
        ;;
    pacman)
        info "refreshing pacman databases"
        run_root pacman -Sy --noconfirm
        pkg_install python python-pip sdl2 sdl2_image sdl2_mixer sdl2_ttf base-devel
        ;;
    dnf)
        info "installing development groups (DNF)"
        run_root dnf -y groupinstall "Development Tools" || true
        pkg_install python3 python3-pip SDL2-devel gcc gcc-c++ pkgconf-pkg-config
        ;;
    yum)
        info "enabling EPEL repository"
        run_root yum install -y epel-release || true
        run_root yum groupinstall -y "Development Tools" || true
        pkg_install python3 python3-pip SDL2-devel gcc gcc-c++ pkgconfig
        ;;
    zypper)
        info "installing patterns and libraries (Zypper)"
        run_root zypper --non-interactive install patterns-devel-base-devel_basis || true
        pkg_install python3 python3-pip python3-devel libSDL2-devel gcc gcc-c++ pkgconfig
        ;;
    brew)
        if ! command -v brew >/dev/null 2>&1; then
            warn "Homebrew not found - install it from https://brew.sh and re-run"
            warn "continuing with whatever Python is already available"
        else
            pkg_install python3 sdl2 sdl2_image sdl2_mixer sdl2_ttf
        fi
        ;;
    *)
        warn "no known package manager - assuming toolchain is present"
        ;;
esac
ok "system dependency phase complete"

# ---------------------------------------------------------------------------
#  Python interpreter
# ---------------------------------------------------------------------------
step "Python interpreter"
PY_BIN=""
for c in python3 python; do
    if command -v "$c" >/dev/null 2>&1; then
        if "$c" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, '"$PYTHON_MIN_MINOR"', 0) else 1)' 2>/dev/null; then
            PY_BIN="$c"; break
        fi
    fi
done
if [ -z "$PY_BIN" ]; then
    err "Python >= 3.${PYTHON_MIN_MINOR} was not found on this system"
    err "install it via your package manager and re-run ./setup.sh"
    exit 1
fi
PY_VER_STR="$("$PY_BIN" --version 2>&1)"
say "selected     : ${C_BOLD}${PY_BIN}${C_RESET} -> ${PY_VER_STR}"
say "interpreter  : $("$PY_BIN" -c 'import sys; print(sys.executable)')"
ok "python check passed"

# ---------------------------------------------------------------------------
#  Virtual environment
# ---------------------------------------------------------------------------
step "Virtual environment (.venv)"
if [ -x "$VENV_DIR/bin/python" ]; then
    info "existing .venv detected - refreshing pip toolchain inside it"
elif ! "$PY_BIN" -m venv "$VENV_DIR" 2>/dev/null; then
    warn "venv creation failed - installing python3-venv"
    case "$PKG_FAMILY" in
        apt) pkg_install python3-venv ;;
        *)   warn "cannot auto-install venv support on ${DIST_ID}" ;;
    esac
    "$PY_BIN" -m venv "$VENV_DIR" || { err "could not create virtual environment"; exit 1; }
fi
VPY="$VENV_DIR/bin/python"
[ -x "$VPY" ] || VPY="$VENV_DIR/Scripts/python.exe"   # unusual layouts
[ -x "$VPY" ] || { err "venv python missing at $VENV_DIR/bin/python"; exit 1; }
"$VPY" -m pip install --quiet --upgrade $([ -n "$PIP_MIRROR" ] && echo "-i $PIP_MIRROR") pip setuptools wheel
ok "environment ready: $("$VPY" --version 2>&1)"

# ---------------------------------------------------------------------------
#  Game requirements
# ---------------------------------------------------------------------------
step "Game requirements"
REQ_FILE="requirements.txt"
if [ ! -f "$REQ_FILE" ]; then
    warn "requirements.txt not found - falling back to pinned default set"
    printf 'pygame>=2.5,<3\n' > "$REQ_FILE"
fi
say "manifest:"
sed 's/^/      /' "$REQ_FILE"
info "resolving and installing (first run compiles SDL bindings - please wait)"
"$VPY" -m pip install --upgrade $([ -n "$PIP_MIRROR" ] && echo "-i $PIP_MIRROR") -r "$REQ_FILE"
ok "python dependencies installed"

# ---------------------------------------------------------------------------
#  Integrity verification
# ---------------------------------------------------------------------------
step "Integrity verification"
MISSING=""
for f in LICENSE README.md INSTALL.md COVER.md txt; do
    [ -e "$f" ] || MISSING="$MISSING $f"
done
if [ -n "$MISSING" ]; then
    warn "documentation incomplete:${MISSING}"
else
    ok "repository layout verified"
fi
FILES="$(find game -name '*.py' 2>/dev/null | wc -l | tr -d ' ')"
if [ "$FILES" -gt 0 ]; then
    ok "game sources found: ${C_BOLD}${FILES}${C_RESET} modules under game/"
else
    err "no game sources under game/ - cannot continue"
    exit 1
fi
info "byte-compiling all modules (catches syntax errors early)"
"$VPY" -m compileall -q game >/dev/null
ok "sources byte-compile cleanly"
info "importing engine entry point"
SDL_VIDEODRIVER=dummy "$VPY" - <<'PYEOF'
import os, sys
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
try:
    import pygame  # noqa: F401
except Exception as exc:
    print(f"  [XX]   pygame import failed: {exc}")
    sys.exit(1)
from game.engine import app  # noqa: F401
print("  [OK]   game.engine.app imports successfully")
PYEOF

# ---------------------------------------------------------------------------
#  Epilogue
# ---------------------------------------------------------------------------
step "Summary"
say "python         : ${PY_VER_STR}"
say "dependencies   : $(wc -l < "$REQ_FILE" | tr -d ' ') manifest entries satisfied"
say "verification   : layout, byte-compile, engine import - all green"
say "save location  : ~/.abyss_economy_save.json"
usage_footer
printf '\n  %sruntime controls:%s  WASD move | mouse aim | LMB light | RMB heavy\n' "$C_BOLD" "$C_RESET"
say "TAB inventory | E campfire | ESC pause | Q rune slot | R reload dungeon"

ACTUAL_PY="$("$VPY" --version 2>&1 | awk '{print $2}')"
MAJOR="$(echo "$ACTUAL_PY" | cut -d. -f1)"
MINOR="$(echo "$ACTUAL_PY" | cut -d. -f2)"
if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge "$PYTHON_MIN_MINOR" ]; then
    ok "you are cleared for descent"
else
    warn "detected ${ACTUAL_PY} inside .venv - expected >= 3.${PYTHON_MIN_MINOR}"
fi

if [ "$RUN_GAME" -eq 1 ]; then
    printf '\n'
    hr
    printf '%s launching the abyss %s\n' "$C_HCYAN" "$C_RESET"
    hr
    sleep 1
    exec "$VPY" -m "$GAME_MODULE"
else
    say ""
    say "launch whenever you are ready:   ${C_BOLD}./setup.sh${C_RESET}   or   ${C_BOLD}${VPY} -m ${GAME_MODULE}${C_RESET}"
fi
exit 0

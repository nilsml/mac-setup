#!/bin/sh
set -eu

# Denne kroken kjøres kun i sandboxen som agent. Ikke erstatt kitets AGENTS.md
# eller opencode.json, som kan inneholde generert modell- og credential-oppsett.
config="$HOME/.config/opencode"
mkdir -p "$config" "$HOME/.config/zsh" "$HOME/.local/state/zsh"

seed() {
    source=$1
    target=$2
    if [ ! -e "$target" ]; then
        cp "$source" "$target"
    fi
}

seed /opt/personal/files/zshrc "$HOME/.zshrc"
seed /opt/personal/files/aliases.zsh "$HOME/.config/zsh/aliases.zsh"
seed /opt/personal/files/cli.json "$config/cli.json"
seed /opt/personal/files/preferences.md "$config/preferences.md"

# Ikke overskriv en eksisterende Neovim-konfigurasjon eller installerte plugins.
if [ ! -e "$HOME/.config/nvim" ]; then
    cp -R /opt/personal/files/nvim "$HOME/.config/nvim"
fi
for plugin in start/packer.nvim start/lualine.nvim start/nord-vim opt/nvim-web-devicons; do
    destination="$HOME/.local/share/nvim/site/pack/packer/$plugin"
    if [ ! -e "$destination" ]; then
        mkdir -p "$(dirname "$destination")"
        cp -R "/opt/personal/nvim/site/pack/packer/$plugin" "$destination"
    fi
done

# Bevar Docker-genererte innstillinger og legg bare til shell og instruksjoner.
python3 - "$config/opencode.json" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
config = json.loads(path.read_text()) if path.exists() else {}
config.setdefault("$schema", "https://opencode.ai/config.json")
config.setdefault("shell", "/usr/bin/zsh")
instructions = config.setdefault("instructions", [])
if not isinstance(instructions, list):
    raise SystemExit("Forventet instructions som liste. Ingen konfigurasjon endret.")
preferences = "/home/agent/.config/opencode/preferences.md"
if preferences not in instructions:
    instructions.append(preferences)
path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n")
PY

# twg lenker skillene inn for OpenCode. Eksisterende skills oppdateres bare.
twg skills install --yes --agent opencode >/dev/null

if [ -f /opt/personal/files/powerline/tui.tsx ]; then
    mkdir -p "$config/plugins/powerline"
    seed /opt/personal/files/powerline/tui.tsx "$config/plugins/powerline/tui.tsx"
else
    echo "Powerline mangler i byggkonteksten." >&2
    exit 1
fi

#!/bin/sh
set -eu

# Kjøres inne i sandboxen. Ingen modellkall eller skriving til prosjektet.
test "$(id -un)" = agent
test "$HOME" = /home/agent
opencode --version
for tool in zsh starship git curl node npm npx python3 uv eza nvim gh jq rg yamllint actionlint shellcheck; do
    command -v "$tool"
done
node -e 'if (process.versions.node.split(".")[0] !== "24") process.exit(1)'
uv --version
actionlint -version
yamllint --version
shellcheck --version
zsh -n "$HOME/.zshrc"
zsh -n "$HOME/.config/zsh/aliases.zsh"
test -f "$HOME/.config/opencode/plugins/powerline/tui.tsx"
python3 - <<'PY'
import json
import pathlib

root = pathlib.Path.home() / ".config/opencode"
cli = json.loads((root / "cli.json").read_text())
config = json.loads((root / "opencode.json").read_text())
assert cli["theme"]["name"] == "nord"
assert config["shell"] == "/usr/bin/zsh"
assert (root / "preferences.md").as_posix() in config["instructions"]
print("Konfigurasjon OK. Modelltilgang og visuell TUI må testes separat.")
PY

#!/usr/bin/env bash
# Bootstrap a new Mac. Safe to re-run: every step checks before it acts.
#
# Preconditions:
#   - Signed in to the App Store (needed for the `mas` entries in Brewfile)
#   - Terminal has Full Disk Access (System Settings > Privacy & Security)
#
# Usage: ./osx_bootstrap.sh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ZSH_CUSTOM="${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}"

log() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }

# Append a line to a file unless it is already there.
ensure_line() {
  local line="$1" file="$2"
  touch "$file"
  grep -qxF "$line" "$file" || echo "$line" >>"$file"
}

# Clone a git repo unless the target directory already exists.
ensure_clone() {
  local url="$1" dest="$2"
  [[ -d "$dest" ]] || git clone --depth 1 "$url" "$dest"
}

install_xcode_clt() {
  log "Xcode Command Line Tools"
  if xcode-select -p >/dev/null 2>&1; then
    echo "already installed"
  else
    xcode-select --install
    echo "Finish the installer dialog, then re-run this script."
    exit 1
  fi
}

install_homebrew() {
  log "Homebrew"
  if ! command -v brew >/dev/null 2>&1 && [[ ! -x /opt/homebrew/bin/brew ]]; then
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  fi
  ensure_line 'eval "$(/opt/homebrew/bin/brew shellenv)"' "$HOME/.zprofile"
  eval "$(/opt/homebrew/bin/brew shellenv)"
  brew update
}

install_bundle() {
  log "Brewfile (formulae, casks, App Store, VS Code, uv, npm)"
  brew bundle install --file="$REPO_DIR/Brewfile"
}

install_oh_my_zsh() {
  log "oh-my-zsh + plugins"
  if [[ ! -d "$HOME/.oh-my-zsh" ]]; then
    RUNZSH=no KEEP_ZSHRC=yes sh -c \
      "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"
  fi
  local plugin
  for plugin in zsh-autosuggestions zsh-completions zsh-syntax-highlighting; do
    ensure_clone "https://github.com/zsh-users/$plugin" "$ZSH_CUSTOM/plugins/$plugin"
  done
}

install_tmux_plugins() {
  log "tmux plugin manager"
  ensure_clone https://github.com/tmux-plugins/tpm "$HOME/.tmux/plugins/tpm"
}

install_dotfiles() {
  log "dotfiles"
  local dir="$HOME/dotfiles"
  if [[ ! -d "$dir" ]]; then
    # dotfiles is a private repo, so log in to GitHub first
    gh auth status >/dev/null 2>&1 || gh auth login
    gh repo clone nilsml/dotfiles "$dir"
  fi
  if [[ -f "$dir/install.sh" ]]; then
    bash "$dir/install.sh"
  else
    echo "WARNING: $dir/install.sh not found, skipping dotfiles install." >&2
  fi
}

main() {
  install_xcode_clt
  install_homebrew
  install_bundle
  install_oh_my_zsh
  install_tmux_plugins
  install_dotfiles
  log "Cleanup"
  brew cleanup
  brew doctor || true
  log "Done. Restart the terminal."
}

main "$@"

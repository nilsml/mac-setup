# mac-setup

My setup for a new Mac. Everything installable lives in `Brewfile`; `osx_bootstrap.sh` installs the prerequisites and runs it. The script is safe to re-run.

## New Mac

1. Sign in to the App Store (required for the `mas` entries).
2. Give Terminal Full Disk Access: System Settings → Privacy & Security.
3. Run:
   ```bash
   git clone https://github.com/nilsml/mac-setup.git && cd mac-setup
   ./osx_bootstrap.sh
   ```
   The first run may stop after installing Xcode Command Line Tools. Run it again when that is done.
4. Copy `.zshrc` and `.gitconfig` to `~/` and replace the `YOUR_*` values.
5. Manual: iTerm2 profile/font/hotkey, VS Code Settings Sync.

## What gets installed

`Brewfile` covers:

| Type | Installed via |
|---|---|
| CLI tools (`brew`) | Homebrew formulae |
| Apps (`cask`) | Homebrew casks, including Nerd Fonts |
| App Store apps (`mas`) | `mas` |
| VS Code extensions (`vscode`) | `code` |
| Python tools (`uv`) | `uv tool` |
| Global npm packages (`npm`) | `npm -g` |

Plus oh-my-zsh with autosuggestions, completions and syntax-highlighting, and tmux plugin manager.

## Keeping it up to date

On the current Mac, regenerate the Brewfile and commit the diff:

```bash
brew bundle dump --file=Brewfile --describe --force
```

Check what is missing or extra compared to the machine:

```bash
brew bundle check --file=Brewfile --verbose
brew bundle cleanup --file=Brewfile   # lists what is installed but not in Brewfile
```

## Terminal

- Terminal: iTerm2 (Alacritty also installed)
- Shell: zsh + oh-my-zsh
- Prompt: [starship](https://starship.rs)
- Font: Fira Code Nerd Font

## Git

See `.gitconfig`: rebase on pull, VS Code as editor and difftool, log aliases.

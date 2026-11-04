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
4. Dotfiles and Claude config come from [nilsml/dotfiles](https://github.com/nilsml/dotfiles): the script clones it to `~/Dev/dotfiles` and runs its `install.sh`.
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

Plus oh-my-zsh with autosuggestions, completions and syntax-highlighting, tmux plugin manager, and the dotfiles repo.

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

## Before wiping the old Mac

- `brew bundle dump --file=Brewfile --describe --force` and commit
- In dotfiles: `./claude/capture.sh`, review `git diff`, commit
- Back up local-only files (`~/Dev` repos not pushed, `~/Library/Application Support` for apps without sync)
- Sign out of iCloud / Find My, release from Intune, deauthorise licences

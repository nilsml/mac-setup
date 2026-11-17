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
4. Dotfiles, Claude and OpenCode config come from the private repo [nilsml/dotfiles](https://github.com/nilsml/dotfiles). The script asks you to log in with `gh auth login`, clones it to `~/dotfiles` and runs its `install.sh`.
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

## OpenCode in Docker Sandboxes

See **[sbx/README.md](sbx/README.md)** for the complete sandbox guide, including
architecture diagrams, startup flow, content layers, MCP routing, persistence,
credentials and troubleshooting. Each project gets its own replaceable sandbox:

```sh
oc .
```

The launcher creates or reopens the environment and registers missing provider credentials without putting API keys in the repository. Initial setup requires an interactive terminal and provider sign-in on the host.

For a menu of existing OpenCode environments, including opening and confirmed stopping:

```sh
python3 ~/.local/share/opencode-sbx/launcher-mcp-v2/oc.py
```

It also accepts `.`, `list`, `open NAME`, `shell NAME`, and `stop NAME`. The `oc`
shell shortcut is configured separately in dotfiles; the bootstrap does not
install it automatically.

For project startup, `oc.py` mounts the Git working tree root and preserves the
selected subdirectory as the starting directory. Nested repositories keep their
own identity. Outside Git, it uses the selected directory. Linked worktrees and
other repositories with external Git metadata are currently rejected without
adding mounts. Existing environments remain accessible via `open NAME`.
Direct `start.py` invocation retains explicit directory selection.

`capabilities [PATH|NAME]` previews the expected content layers using a private
host catalog. This currently selects layers only; it does not install or verify
skills, instructions, MCP servers, or agents.

New environments launched through `oc.py` can use live, read-only content
mounts from a format-2 host catalog. Existing environments are not retrofitted.
The launcher and host catalog must be outside the writable project mount.
See [the content mount contract](sbx/CONTENT-MOUNTS.md) for activation,
agent registration, collision checks, and limitations.

Browse and Rovo are discovered through sbx's existing `mcp-gateway`. Logseq uses
a separate connection for native per-agent tool permissions. See
[the MCP guide](sbx/MCP.md) for transports and security limitations.

## Before wiping the old Mac

- `brew bundle dump --file=Brewfile --describe --force` and commit
- In dotfiles: `./claude/capture.sh`, review `git diff`, commit
- Back up local-only files (`~/Dev` repos not pushed, `~/Library/Application Support` for apps without sync)
- Sign out of iCloud / Find My, release from Intune, deauthorise licences

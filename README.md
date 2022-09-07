# mac-setup

**_Michael's subjective approach to setting up a new Mac for work_**

I use [Homebrew](https://brew.sh/), `shell` and `git` to install all the packages & applications I need.

I made a script (`osx_bootstrap.sh`) which does all this for me, leaving just a few steps for manual settings afterwards.

Browse all the formulas (packages) or casks (applications) [here](https://formulae.brew.sh/) and edit `osx_bootstrap.sh` to your liking.

## The gist

1. Open `Terminal.app`
2. Run command `chmod +x osx_bootstrap.sh`
3. Run command `./osx_bootstrap.sh`
4. Sit back and drink coffee ☕️ while your mac bootstraps
5. Copy dotfiles `.gitconfig` & `.zshrc` to `~/`
   1. Replace personal environment variables starting with `YOUR_`
6. Do some manual settings in `iTerm2` & `Visual Studio Code`

## Stuff explained

### Font

A [Nerd Font](https://www.nerdfonts.com/) is recommended because of patched glyphs (icons) in the font making terminal stuff awesomesauce. I recommend Fira Code, but its up to your preference.

### Applications

- alfred
- 1password
- magnet
- amphetamine
- rocket

### Microsoft Office

To get any Microsoft Office application (except Teams) activated with our enrolled devices you need to go open `Bouvet Self Servie` and run "Microsoft Intune Integration" to enroll your device so that Microsoft licenses are activated. After this is done all applications should activated on first open.

### Terminal

This chapter is about setting up your [terminal, shell and prompt (command-line)](https://www.geeksforgeeks.org/difference-between-terminal-console-shell-and-command-line/).

- Terminal: [iTerm2](https://iterm2.com/)
- Shell: [zsh](https://ohmyz.sh/)
- prompt: [starship](https://starship.rs)

#### iTerm2

- Go to `Preferences/Profiles`
- Create new profile (delete old one)
- Got to `Preferences/Profiles/Colors` to set your preferred font
- Go to `Preferences/Profiles/Text` to add a color theme if you want
  - I use Snazzy [iTerm 2](https://github.com/sindresorhus/iterm2-snazzy) theme which is the same theme i use in my [Visual Studio Code](https://marketplace.visualstudio.com/items?itemName=alexanderbast.vscode-snazzy)

##### Quake-terminal

You can configure iTerm2 to show/hide with a global shortcut.

- Go to `Preferences/Keys/HotKey` and enable "Show/hide all windows with a system-wide hotkey"
  - I use `ctrl+'`.
- Go to `Preferences/Profiles/Window` and set "Space" to "All Spaces"

#### Zsh

Configure your zsh with plugins, themes and other usefull stuff. Look at `.zshrc` for example.

- autosuggestions
- syntax-highlights
- completions
- z
- Make some aliases

#### Starship

This replaces your prompt. I just use it out of the box as it gives me all I need. Checkout [starship](https://starship.rs/) for more configuration options.

#### IDE

I use `Visual Studio Code`.

- Recommend using a font with ligatures
- Extensions and settings are subjective
- Use settings sync with your Github account

## Git

Look at my global `.gitconfig` for examples.

- Recommend rebase on pull
- Use your IDE for git commit edits
- Prettify

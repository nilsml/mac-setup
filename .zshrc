# If you come from bash you might have to change your $PATH.
# export PATH=$HOME/bin:/usr/local/bin:$PATH

# Path to your oh-my-zsh installation.
export ZSH="$HOME/.oh-my-zsh"
# Theme
ZSH_THEME=""

# Styling
zstyle ':completion:*' menu select

# Plugins
plugins=(
  git
  gh
  z
  docker
  bundler
  dotenv
  macos
  ruby
  npm
  zsh-autosuggestions
  zsh-syntax-highlighting
  zsh-completions
)

autoload -U compinit && compinit

# Reload changes
source $ZSH/oh-my-zsh.sh

# Aliases
alias c="code ."
alias pull="git stash && git pull && git stash pop"
alias gprune="git remote prune origin && git branch -vv | grep 'origin/.*: gone]' | awk '{print $1}' | xargs git branch -D"
export PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin

# ~/.zshrc

eval "$(starship init zsh)"

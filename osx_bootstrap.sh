#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -euo pipefail
IFS=$'\n\t'

# inspired by
# https://gist.github.com/codeinthehole/26b37efa67041e1307db
# https://github.com/why-jay/osx-init/blob/master/install.sh
# https://github.com/timsutton/osx-vm-templates/blob/master/scripts/xcode-cli-tools.sh

# PRECONDITIONS
# 1)
# make sure the file is executable
# chmod +x osx_bootstrap.sh
#
# 2)
# Your password may be necessary for some packages
#
# 3)
# https://docs.brew.sh/Installation#macos-requirements
# xcode-select --install
# (_xcode-select installation_ installs git already, however git will be installed via brew packages as well to install as much as possible the brew way
#  this way you benefit from frequent brew updates)
#
# 4) don't let the “Operation not permitted” error bite you
# Please make sure you system settings allow the termianl full disk access
# https://osxdaily.com/2018/10/09/fix-operation-not-permitted-terminal-error-macos/

# `set -eu` causes an 'unbound variable' error in case SUDO_USER is not set
SUDO_USER=$(whoami)

# Check for Homebrew, install if not installed
if test ! $(which brew); then
    echo "Installing homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

brew update
brew upgrade

# find the CLI Tools update
echo "find CLI tools update"
PROD=$(softwareupdate -l | grep "\*.*Command Line" | head -n 1 | awk -F"*" '{print $2}' | sed -e 's/^ *//' | tr -d '\n') || true
# install it
if [[ ! -z "$PROD" ]]; then
    softwareupdate -i "$PROD" --verbose
fi

PACKAGES=(
    node
    docker
    git
    cocoapods
    gh
    grep
    tree
    jq
    flutter
    starship
)

echo "Installing packages..."
brew install ${PACKAGES[@]}

CASKS=(
    alfred
    figma
    iterm2
    visual-studio-code
    microsoft-teams
    microsoft-edge
    google-chrome
    slack
    ngrok
    insomnia
    spotify
    rocket
    vlc
)

echo "Installing cask apps..."
sudo -u $SUDO_USER brew install --cask ${CASKS[@]}

#sudo -u $SUDO_USER brew install --cask docker
#or
#brew install colima

echo "Install Nerd Font Fira Code"
brew tap homebrew/cask-fonts
brew install --cask font-fira-code-nerd-font

echo "Installing finder improvements"
brew install --cask qlcolorcode qlimagesize qlmarkdown qlvideo quicklook-csv quicklook-json
brew install --cask suspicious-package

# Check for ohmyzsh, install if not installed
if test ! $(which zsh); then
    echo "Installing ohmyzsh..."
    /bin/bash -c "$(curl -fsSL https://raw.github.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"
fi

echo "Installing additional zsh plugins"
git clone https://github.com/zsh-users/zsh-autosuggestions ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/zsh-autosuggestions
git clone https://github.com/zsh-users/zsh-completions ${ZSH_CUSTOM:=~/.oh-my-zsh/custom}/plugins/zsh-completions
git clone https://github.com/zsh-users/zsh-syntax-highlighting.git ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/zsh-syntax-highlighting

echo "Installing global npm packages..."
sudo -u $SUDO_USER npm install pnpm -g

echo "Installing mac store app installer"
brew install mas

echo "Installing mac store apps"
# Amphetamine
mas install 937984704
# Magnet
mas install 441258766
# Xcode
mas install 497799835
# Remote Desktop
mas install 1295203466

echo "Cleaning up"
brew cleanup
echo "Ask the doctor"
brew doctor

echo "osx bootstrapping done"

# please see also the accompanying blog post
# https://www.lotharschulz.info/2021/05/11/macos-setup-automation-with-homebrew/

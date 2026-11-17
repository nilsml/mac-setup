# Stabilt byggegrunnlag for mixinens tillegg, ikke workloadens OpenCode-versjon.
FROM docker.io/sbx/opencode@sha256:12a8938cd96bc90ec24881119a3483913ec894672e56d3a7d40a0955daa040db

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       zsh zsh-autosuggestions zsh-syntax-highlighting \
       eza neovim python3 python3-venv yamllint shellcheck \
       ca-certificates curl git unzip xz-utils \
    && rm -rf /var/lib/apt/lists/*

ARG TARGETARCH
ARG NODE_VERSION=24.22.3
ARG UV_VERSION=0.13.9
ARG ACTIONLINT_VERSION=1.7.12
RUN set -eu; \
    case "$TARGETARCH" in \
      arm64) node_arch=arm64; uv_arch=aarch64 ;; \
      amd64) node_arch=x64; uv_arch=x86_64 ;; \
      *) echo "Ukjent arkitektur: $TARGETARCH" >&2; exit 1 ;; \
    esac; \
    mkdir -p /tmp/dev-tools /opt/node; \
    cd /tmp/dev-tools; \
    node_archive="node-v${NODE_VERSION}-linux-${node_arch}.tar.xz"; \
    curl -fsSLO "https://nodejs.org/dist/v${NODE_VERSION}/${node_archive}"; \
    curl -fsSLo node-checksums.txt "https://nodejs.org/dist/v${NODE_VERSION}/SHASUMS256.txt"; \
    grep "  ${node_archive}\$" node-checksums.txt | sha256sum -c -; \
    tar -xJf "$node_archive" -C /opt/node --strip-components=1; \
    for tool in node npm npx; do ln -s "/opt/node/bin/$tool" "/usr/local/bin/$tool"; done; \
    uv_archive="uv-${uv_arch}-unknown-linux-musl.tar.gz"; \
    curl -fsSLO "https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/${uv_archive}"; \
    curl -fsSLo uv-checksums.txt "https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/sha256.sum"; \
    grep " [*]${uv_archive}\$" uv-checksums.txt | sha256sum -c -; \
    tar -xzf "$uv_archive"; \
    cp "uv-${uv_arch}-unknown-linux-musl/uv" /usr/local/bin/uv; \
    actionlint_archive="actionlint_${ACTIONLINT_VERSION}_linux_${TARGETARCH}.tar.gz"; \
    curl -fsSLO "https://github.com/rhysd/actionlint/releases/download/v${ACTIONLINT_VERSION}/${actionlint_archive}"; \
    curl -fsSLo actionlint-checksums.txt "https://github.com/rhysd/actionlint/releases/download/v${ACTIONLINT_VERSION}/actionlint_${ACTIONLINT_VERSION}_checksums.txt"; \
    grep " ${actionlint_archive}\$" actionlint-checksums.txt | sha256sum -c -; \
    tar -xzf "$actionlint_archive" -C /usr/local/bin actionlint; \
    node --version; npm --version; uv --version; actionlint -version; \
    rm -rf /tmp/dev-tools

ARG STARSHIP_VERSION=1.22.1
RUN set -eu; \
    case "$TARGETARCH" in \
      arm64) target=aarch64-unknown-linux-musl ;; \
      amd64) target=x86_64-unknown-linux-musl ;; \
      *) echo "Ukjent arkitektur: $TARGETARCH" >&2; exit 1 ;; \
    esac; \
    curl -fsSL "https://github.com/starship/starship/releases/download/v${STARSHIP_VERSION}/starship-${target}.tar.gz" \
      -o /tmp/starship.tar.gz; \
    tar -xzf /tmp/starship.tar.gz -C /usr/local/bin starship; \
    rm /tmp/starship.tar.gz

ARG OH_MY_ZSH_COMMIT=6010fb6260f359e71d99ba25f05f9215809b3ed2
RUN git init /opt/oh-my-zsh \
    && git -C /opt/oh-my-zsh remote add origin https://github.com/ohmyzsh/ohmyzsh.git \
    && git -C /opt/oh-my-zsh fetch --depth 1 origin "$OH_MY_ZSH_COMMIT" \
    && git -C /opt/oh-my-zsh checkout --detach FETCH_HEAD \
    && rm -rf /opt/oh-my-zsh/.git

# Samme pluginversjoner som i Macens aktive Packer-oppsett, uten runtime-nettverk.
RUN set -eu; \
    install_plugin() { \
      destination="$1"; repository="$2"; revision="$3"; \
      git init "$destination"; \
      git -C "$destination" remote add origin "$repository"; \
      git -C "$destination" fetch --depth 1 origin "$revision"; \
      git -C "$destination" checkout --detach FETCH_HEAD; \
    }; \
    root=/opt/personal/nvim/site/pack/packer; \
    install_plugin "$root/start/packer.nvim" https://github.com/wbthomason/packer.nvim ea0cc3c59f67c440c5ff0bbe4fb9420f4350b9a3; \
    install_plugin "$root/start/lualine.nvim" https://github.com/nvim-lualine/lualine.nvim 47f91c416daef12db467145e16bed5bbfe00add8; \
    install_plugin "$root/start/nord-vim" https://github.com/arcticicestudio/nord-vim f13f5dfbb784deddbc1d8195f34dfd9ec73e2295; \
    install_plugin "$root/opt/nvim-web-devicons" https://github.com/kyazdani42/nvim-web-devicons 746ffbb17975ebd6c40142362eee1b0249969c5c

COPY files/ /opt/personal/files/
COPY install.sh /opt/personal/install.sh
USER agent

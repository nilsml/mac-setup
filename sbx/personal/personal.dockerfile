# Samme base som testsandboxen. Oppdater digest og test sammen med OpenCode.
FROM docker.io/sbx/opencode@sha256:12a8938cd96bc90ec24881119a3483913ec894672e56d3a7d40a0955daa040db

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       zsh zsh-autosuggestions zsh-syntax-highlighting \
       eza neovim nodejs npm python3 python3-venv \
       ca-certificates curl git unzip \
    && rm -rf /var/lib/apt/lists/*

ARG TARGETARCH
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

COPY files/ /opt/personal/files/
COPY install.sh /opt/personal/install.sh
USER agent

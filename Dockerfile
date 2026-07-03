FROM node:24-bookworm-slim

LABEL org.opencontainers.image.title="pi-sandbox" \
      org.opencontainers.image.description="pi coding agent sandbox image" \
      org.opencontainers.image.source="https://github.com/Ponchoalfonso/pi-sandbox" \
      dev.pi-sandbox.prunable="true"

RUN apt-get update \
  && apt-get install -y --no-install-recommends bash ca-certificates fd-find git python3 ripgrep wget \
  && ln -sf /usr/bin/fdfind /usr/local/bin/fd \
  && mkdir -p -m 755 /etc/apt/keyrings \
  && wget -nv -O /etc/apt/keyrings/githubcli-archive-keyring.gpg https://cli.github.com/packages/githubcli-archive-keyring.gpg \
  && chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg \
  && mkdir -p -m 755 /etc/apt/sources.list.d \
  && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" > /etc/apt/sources.list.d/github-cli.list \
  && apt-get update \
  && apt-get install -y --no-install-recommends gh \
  && rm -rf /var/lib/apt/lists/*
RUN npm install -g --ignore-scripts @earendil-works/pi-coding-agent pnpm@latest-11

WORKDIR /workspace
ENTRYPOINT ["pi"]

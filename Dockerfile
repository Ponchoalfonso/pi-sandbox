FROM node:24-bookworm-slim

LABEL org.opencontainers.image.title="pi-sandbox" \
      org.opencontainers.image.description="pi coding agent sandbox image" \
      org.opencontainers.image.source="https://github.com/Ponchoalfonso/pi-sandbox" \
      dev.pi-sandbox.prunable="true"

RUN apt-get update \
  && apt-get install -y --no-install-recommends bash ca-certificates git ripgrep \
  && rm -rf /var/lib/apt/lists/*
RUN npm install -g --ignore-scripts @earendil-works/pi-coding-agent
RUN pi install npm:pi-subagents
RUN pi install npm:pi-intercom
RUN pi install npm:pi-vim
RUN pi install npm:pi-web-access

WORKDIR /workspace
ENTRYPOINT ["pi"]

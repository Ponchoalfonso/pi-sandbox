# pi-sandbox

Docker sandbox for running [`pi`](https://pi.dev) with your local pi auth/config mounted in.

## Image

Default image used by the launcher:

```text
ghcr.io/ponchoalfonso/pi-sandbox:latest
```

Build locally:

```bash
docker build -t pi-sandbox:latest .
```

## Run

```bash
scripts/pi-sandbox.py
```

Pass args to `pi` after `--`:

```bash
scripts/pi-sandbox.py -- -p "summarize this repo"
```

Useful flags:

```bash
scripts/pi-sandbox.py --no-pull
scripts/pi-sandbox.py --workspace ~/src/project
scripts/pi-sandbox.py --pi-home ~/.pi/agent
scripts/pi-sandbox.py --pi-home volume:pi-agent-volume
scripts/pi-sandbox.py --context-home ~/docs
scripts/pi-sandbox.py --gh-config ~/.config/gh
scripts/pi-sandbox.py --prune
```

Mounts:

| Host | Container | Notes |
|---|---|---|
| workspace | same absolute path as host | read/write |
| pi home | `$HOME/.pi/agent` | auth/config/packages/sessions |
| pnpm home | `$HOME/.local/share/pnpm` | tmpfs; pnpm binaries/store; discarded when container exits |
| GitHub CLI config | `$HOME/.config/gh` | read-only; omitted by default |
| context home | `$HOME/docs` | read-only; omitted by default |

Inside the container, `HOME` is set to your host home path, so pi shows familiar paths like `~/dev/pi-sandbox`. The launcher also sets `PI_CODING_AGENT_DIR=$HOME/.pi/agent` explicitly.

The launcher mirrors pnpm's usual Linux user-level location inside the container by setting `PNPM_HOME=$HOME/.local/share/pnpm` and `store-dir=$HOME/.local/share/pnpm/store`. That path is mounted as container-only tmpfs, so pnpm does not create project-local `.pnpm-store` directories and the pnpm store is discarded when the container exits.

## Config

Config path follows XDG:

```text
$XDG_CONFIG_HOME/pi-sandbox.toml
```

Default fallback:

```text
~/.config/pi-sandbox.toml
```

Create an opinionated config:

```bash
scripts/pi-sandbox.py --scaffold-config
```

Example:

```toml
image = "ghcr.io/ponchoalfonso/pi-sandbox:latest"
pull = true
pi-home = "~/.pi/agent"
context-home = "~/docs"
gh-config = "~/.config/gh"
```

Precedence:

```text
flags > environment variables > config > built-in defaults
```

Supported env vars:

```text
XDG_CONFIG_HOME
PI_SANDBOX_IMAGE
PI_SANDBOX_PULL
PI_SANDBOX_WORKSPACE
PI_SANDBOX_PI_HOME
PI_SANDBOX_CONTEXT_HOME
PI_SANDBOX_GH_CONFIG
```

## Pulling and pruning

By default the launcher pulls the configured image before running. For `:latest`, this updates the local tag to the registry's current digest.

Prune old dangling sandbox images:

```bash
scripts/pi-sandbox.py --prune
```

This only prunes dangling images with:

```text
dev.pi-sandbox.prunable=true
```

## GitHub Container Registry

The workflow publishes to GHCR on:

- push to `main`
- daily scheduled poll
- manual workflow dispatch

It tags images as:

```text
latest
<latest upstream earendil-works/pi release tag>
```

It also removes old package versions, keeping the latest 3.

## Auth and extensions

The launcher mounts pi home into the container:

```text
~/.pi/agent -> $HOME/.pi/agent
```

That means your host pi auth, config, extensions, packages, and sessions are available in the container. If you use a named Docker volume for `--pi-home`, that volume controls what pi packages/extensions are available.

Set `--gh-config`, `PI_SANDBOX_GH_CONFIG`, or `gh-config` in config to mount your host GitHub CLI config read-only and set `GH_CONFIG_DIR=$HOME/.config/gh`, so the sandbox can reuse your host GitHub CLI session. The scaffolded config points this at your XDG config home's `gh` directory.

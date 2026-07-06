#!/usr/bin/env python3
"""Run pi in a Docker sandbox."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

BUILTIN_IMAGE = "ghcr.io/ponchoalfonso/pi-sandbox:latest"
BUILTIN_PULL = True
BUILTIN_PI_HOME = "~/.pi/agent"
SCAFFOLD_CONTEXT_HOME = "~/docs"
CONFIG_HOME = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")).expanduser()
CONFIG_PATH = CONFIG_HOME / "pi-sandbox.toml"
CONTAINER_HOME = str(Path.home())
SCAFFOLD_GH_CONFIG = str(CONFIG_HOME / "gh")
CONTAINER_GH_CONFIG = f"{CONTAINER_HOME}/.config/gh"
CONTAINER_PNPM_HOME = f"{CONTAINER_HOME}/.local/share/pnpm"

VOLUME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
CONFIG_KEYS = {
    "pull",
    "image",
    "pi-home",
    "pi_home",
    "context-home",
    "context_home",
    "gh-config",
    "gh_config",
    "network",
    "networks",
}
PRUNE_LABEL = "dev.pi-sandbox.prunable=true"


def parse_bool(value: str) -> bool:
    value = value.lower()
    if value in {"1", "true", "yes", "y", "on"}:
        return True
    if value in {"0", "false", "no", "n", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"invalid boolean: {value!r}")


class FirstStoreConst(argparse.Action):
    """Store a const value only for the first occurrence of related flags."""

    def __init__(self, option_strings, dest, const=None, default=None, **kwargs):
        super().__init__(
            option_strings=option_strings,
            dest=dest,
            nargs=0,
            const=const,
            default=default,
            **kwargs,
        )

    def __call__(self, parser, namespace, values, option_string=None):
        seen_attr = f"_{self.dest}_seen"
        if not getattr(namespace, seen_attr, False):
            setattr(namespace, self.dest, self.const)
            setattr(namespace, seen_attr, True)


def mkdir_abs(path: str) -> str:
    resolved = Path(path).expanduser()
    if not resolved.is_absolute():
        resolved = Path.cwd() / resolved
    resolved.mkdir(parents=True, exist_ok=True)
    return str(resolved.resolve())


def is_named_volume(value: str) -> bool:
    return bool(VOLUME_RE.match(value))


def pi_home_mount_source(value: str) -> str:
    if value.startswith("volume:"):
        volume = value.removeprefix("volume:")
        if not is_named_volume(volume):
            raise SystemExit(f"error: invalid Docker volume name: {volume!r}")
        return volume

    if value.startswith("bind:"):
        return mkdir_abs(value.removeprefix("bind:"))

    expanded = os.path.expanduser(value)
    looks_like_path = (
        value in {"~", "."}
        or value.startswith(("/", "~/", "./", "../"))
        or os.sep in value
    )
    if looks_like_path:
        return mkdir_abs(expanded)

    if is_named_volume(value):
        return value

    return mkdir_abs(expanded)


def split_args(argv: list[str]) -> tuple[list[str], list[str]]:
    """Allow `script flags -- pi flags`; unknown script flags are errors."""
    if "--" not in argv:
        return argv, []
    index = argv.index("--")
    return argv[:index], argv[index + 1 :]


def is_disabled(value: Any) -> bool:
    return isinstance(value, str) and value.strip().lower() in {"", "none", "null", "false", "off"}


def none_if_disabled(value: Any) -> str | None:
    if value is None or is_disabled(value):
        return None
    return str(value)


def config_get(config: dict[str, Any], kebab_key: str) -> Any:
    snake_key = kebab_key.replace("-", "_")
    if kebab_key in config:
        return config[kebab_key]
    return config.get(snake_key)


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    with CONFIG_PATH.open("rb") as file:
        data = tomllib.load(file)
    if not isinstance(data, dict):
        raise SystemExit(f"error: config must be a TOML table: {CONFIG_PATH}")
    return {key: value for key, value in data.items() if key in CONFIG_KEYS}


def resolve_value(
    flag_value: Any,
    env_name: str,
    config: dict[str, Any],
    config_key: str,
    fallback: Any,
) -> Any:
    if flag_value is not None:
        return flag_value
    if env_name in os.environ:
        return os.environ[env_name]
    value = config_get(config, config_key)
    if value is not None:
        return value
    return fallback


def resolve_pull(flag_value: bool | None, config: dict[str, Any]) -> bool:
    value = resolve_value(flag_value, "PI_SANDBOX_PULL", config, "pull", BUILTIN_PULL)
    if isinstance(value, bool):
        return value
    return parse_bool(str(value))


def parse_networks(value: Any) -> list[str]:
    if value is None or is_disabled(value):
        return []
    if isinstance(value, str):
        networks = [network.strip() for network in value.split(",")]
    elif isinstance(value, list):
        networks = [str(network).strip() for network in value]
    else:
        raise SystemExit("error: networks must be a string or TOML array")

    networks = [network for network in networks if network]
    if any(is_disabled(network) for network in networks):
        return []
    return networks


def resolve_networks(flag_values: list[str] | None, config: dict[str, Any]) -> list[str]:
    if flag_values is not None:
        return parse_networks(flag_values)
    if "PI_SANDBOX_NETWORKS" in os.environ:
        return parse_networks(os.environ["PI_SANDBOX_NETWORKS"])
    if "PI_SANDBOX_NETWORK" in os.environ:
        return parse_networks(os.environ["PI_SANDBOX_NETWORK"])

    networks = config_get(config, "networks")
    if networks is not None:
        return parse_networks(networks)
    return parse_networks(config_get(config, "network"))


def scaffold_config() -> int:
    if CONFIG_PATH.exists():
        print(f"error: config already exists: {CONFIG_PATH}", file=sys.stderr)
        return 1
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(
        "# pi-sandbox config\n"
        "# Precedence: flags > environment variables > this file.\n"
        f'image = "{BUILTIN_IMAGE}"\n'
        "pull = true\n"
        f'pi-home = "{BUILTIN_PI_HOME}"\n'
        f'context-home = "{SCAFFOLD_CONTEXT_HOME}"\n'
        f'gh-config = "{SCAFFOLD_GH_CONFIG}"\n'
        '# networks = ["myproject_default"]\n',
        encoding="utf-8",
    )
    print(f"created {CONFIG_PATH}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run pi in a Docker sandbox.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--scaffold-config",
        action="store_true",
        help=f"Create an opinionated config at {CONFIG_PATH} and exit.",
    )
    parser.add_argument(
        "--image",
        default=None,
        help=f"Docker image to run. Built-in fallback: {BUILTIN_IMAGE!r}.",
    )
    parser.set_defaults(pull=None)
    parser.add_argument(
        "--pull",
        dest="pull",
        const=True,
        action=FirstStoreConst,
        help="Pull/check the image before running. If repeated with --no-pull, the first flag wins.",
    )
    parser.add_argument(
        "--no-pull",
        dest="pull",
        const=False,
        action=FirstStoreConst,
        help="Do not pull/check the image before running. If repeated with --pull, the first flag wins.",
    )
    parser.add_argument(
        "--workspace",
        default=None,
        help="Host workspace mounted at the same absolute path in the container. Defaults to $PI_SANDBOX_WORKSPACE or current directory.",
    )
    parser.add_argument(
        "--pi-home",
        default=None,
        help=(
            "Host pi config dir or Docker named volume mounted at "
            f"{CONTAINER_HOME}/.pi/agent. Prefix with bind: or volume: to force. "
            f"Built-in fallback: {BUILTIN_PI_HOME!r}."
        ),
    )
    parser.add_argument(
        "--context-home",
        default=None,
        help=(
            f"Host context dir mounted read-only at {CONTAINER_HOME}/docs. "
            "Unset by default; use 'none' to disable an env/config value."
        ),
    )
    parser.add_argument(
        "--gh-config",
        default=None,
        help=(
            f"Host GitHub CLI config dir mounted read-only at {CONTAINER_GH_CONFIG}. "
            "Unset by default; use 'none' to disable an env/config value."
        ),
    )
    parser.add_argument(
        "--network",
        action="append",
        default=None,
        help=(
            "Docker network to attach to. May be repeated. "
            "Unset by default; use 'none' to disable env/config networks."
        ),
    )
    parser.add_argument(
        "--prune",
        action="store_true",
        help=f"Prune dangling Docker images labeled {PRUNE_LABEL!r} before running.",
    )
    return parser


def run_checked(command: list[str]) -> bool:
    return subprocess.run(command).returncode == 0


def main(argv: list[str]) -> int:
    parser = build_parser()
    own_argv, pi_argv_after_separator = split_args(argv)
    args = parser.parse_args(own_argv)
    pi_args = pi_argv_after_separator

    if args.scaffold_config:
        if pi_argv_after_separator:
            print("error: --scaffold-config does not accept pi args", file=sys.stderr)
            return 2
        return scaffold_config()

    config = load_config()

    image = str(resolve_value(args.image, "PI_SANDBOX_IMAGE", config, "image", BUILTIN_IMAGE))
    pull = resolve_pull(args.pull, config)
    workspace = mkdir_abs(args.workspace or os.environ.get("PI_SANDBOX_WORKSPACE", os.getcwd()))
    pi_home_value = str(resolve_value(args.pi_home, "PI_SANDBOX_PI_HOME", config, "pi-home", BUILTIN_PI_HOME))
    context_home_value = none_if_disabled(
        resolve_value(args.context_home, "PI_SANDBOX_CONTEXT_HOME", config, "context-home", None)
    )
    gh_config_value = none_if_disabled(
        resolve_value(args.gh_config, "PI_SANDBOX_GH_CONFIG", config, "gh-config", None)
    )
    networks = resolve_networks(args.network, config)

    pi_home = pi_home_mount_source(pi_home_value)
    context_home = mkdir_abs(context_home_value) if context_home_value is not None else None
    gh_config = mkdir_abs(gh_config_value) if gh_config_value is not None else None

    if pull:
        if not run_checked(["docker", "pull", image]):
            print(
                f"warning: docker pull failed for {image!r}; trying local image",
                file=sys.stderr,
            )
            if not run_checked(["docker", "image", "inspect", image]):
                print(f"error: image {image!r} is not available locally", file=sys.stderr)
                return 1

    if args.prune:
        if not run_checked(["docker", "image", "prune", "--force", "--filter", f"label={PRUNE_LABEL}"]):
            print("error: failed to prune labeled dangling Docker images", file=sys.stderr)
            return 1

    tty_args = ["-i"]
    if sys.stdin.isatty() and sys.stdout.isatty():
        tty_args = ["-it"]

    command = [
        "docker",
        "run",
        "--rm",
        *tty_args,
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        "-e",
        f"HOME={CONTAINER_HOME}",
        "-e",
        f"PI_CODING_AGENT_DIR={CONTAINER_HOME}/.pi/agent",
        "-e",
        "TERM=xterm-256color",
        "-e",
        "COLORTERM=truecolor",
        "-e",
        f"PNPM_HOME={CONTAINER_PNPM_HOME}",
        "-e",
        f"npm_config_store_dir={CONTAINER_PNPM_HOME}/store",
        "-e",
        f"pnpm_config_store_dir={CONTAINER_PNPM_HOME}/store",
        "-v",
        f"{workspace}:{workspace}",
        "--tmpfs",
        f"{CONTAINER_PNPM_HOME}:rw,exec,uid={os.getuid()},gid={os.getgid()},mode=700",
        "-v",
        f"{pi_home}:{CONTAINER_HOME}/.pi/agent",
    ]
    for network in networks:
        command += ["--network", network]
    if gh_config is not None:
        command += [
            "-e",
            f"GH_CONFIG_DIR={CONTAINER_GH_CONFIG}",
            "-v",
            f"{gh_config}:{CONTAINER_GH_CONFIG}:ro",
        ]
    if context_home is not None:
        command += ["-v", f"{context_home}:{CONTAINER_HOME}/docs:ro"]
    command += [
        "-w",
        workspace,
        image,
        *pi_args,
    ]

    os.execvp(command[0], command)
    return 127


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

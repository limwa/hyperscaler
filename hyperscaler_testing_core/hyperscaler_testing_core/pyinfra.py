"""pyinfra helpers used by integration tests."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from hyperscaler_testing_core.commands import CommandResult, run


@dataclass(frozen=True)
class PyinfraTarget:
    """SSH target data rendered into a pyinfra inventory file."""

    name: str
    host: str
    user: str
    ssh_key: Path
    port: int = 22
    strict_host_key_checking: str = "no"
    known_hosts_file: str = "/dev/null"


def write_ssh_inventory(path: Path, target: PyinfraTarget) -> Path:
    """Write a single-host pyinfra SSH inventory file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "hosts = [",
                f"    ({target.name!r}, {{",
                f"        'ssh_hostname': {target.host!r},",
                f"        'ssh_user': {target.user!r},",
                f"        'ssh_key': {str(target.ssh_key)!r},",
                f"        'ssh_port': {target.port!r},",
                "        'ssh_allow_agent': False,",
                "        'ssh_look_for_keys': False,",
                f"        'ssh_known_hosts_file': {target.known_hosts_file!r},",
                f"        'ssh_strict_host_key_checking': {target.strict_host_key_checking!r},",
                "        'ssh_connect_retries': 12,",
                "        'ssh_connect_retry_min_delay': 1.0,",
                "        'ssh_connect_retry_max_delay': 3.0,",
                "    }),",
                "]",
                "",
            ],
        ),
        encoding="utf-8",
    )
    return path


def run_pyinfra(
    inventory_path: Path,
    deploy_path: Path,
    *,
    extra_args: tuple[str, ...] = (),
    timeout_seconds: float | None = None,
) -> CommandResult:
    """Run a pyinfra deploy against an inventory file."""

    return run(
        [
            "pyinfra",
            str(inventory_path),
            str(deploy_path),
            "--yes",
            *extra_args,
        ],
        timeout_seconds=timeout_seconds,
    )

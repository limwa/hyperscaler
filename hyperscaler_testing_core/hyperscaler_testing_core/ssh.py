"""SSH helpers for integration tests."""

from __future__ import annotations

from pathlib import Path
import time

from hyperscaler_testing_core.commands import CommandResult, run


def wait_for_ssh(
    host: str,
    *,
    username: str,
    private_key: Path,
    port: int = 22,
    timeout_seconds: float = 180,
) -> None:
    """Wait until a host accepts non-interactive SSH commands."""

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        result = run_ssh(
            host,
            username=username,
            private_key=private_key,
            port=port,
            command="true",
            check=False,
        )
        if result.returncode == 0:
            return
        time.sleep(2)

    raise TimeoutError(f"SSH did not become available on {username}@{host}:{port}")


def run_ssh(
    host: str,
    *,
    username: str,
    private_key: Path,
    command: str,
    port: int = 22,
    timeout_seconds: float | None = 30,
    check: bool = True,
) -> CommandResult:
    """Run a remote command over SSH."""

    return run(
        [
            "ssh",
            "-i",
            str(private_key),
            "-p",
            str(port),
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=5",
            "-o",
            "IdentitiesOnly=yes",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            f"{username}@{host}",
            command,
        ],
        timeout_seconds=timeout_seconds,
        check=check,
    )

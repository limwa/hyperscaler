"""Small subprocess wrapper used by integration helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
from collections.abc import Sequence


@dataclass(frozen=True)
class CommandResult:
    """Captured command execution result."""

    args: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


class CommandError(RuntimeError):
    """Raised when a checked command exits unsuccessfully."""

    def __init__(self, result: CommandResult) -> None:
        self.result = result
        command = " ".join(result.args)
        super().__init__(
            f"command failed with exit code {result.returncode}: {command}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}",
        )


def run(
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    timeout_seconds: float | None = None,
    check: bool = True,
) -> CommandResult:
    """Run a command and capture stdout/stderr."""

    completed = subprocess.run(
        list(command),
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout_seconds,
        check=False,
    )
    result = CommandResult(
        args=tuple(command),
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )
    if check and result.returncode != 0:
        raise CommandError(result)
    return result


def missing_commands(*commands: str) -> tuple[str, ...]:
    """Return commands that are not available on PATH."""

    return tuple(command for command in commands if shutil.which(command) is None)

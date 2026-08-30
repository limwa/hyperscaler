"""cloud-init seed image helpers."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from hyperscaler_testing_core.commands import run


@dataclass(frozen=True)
class SshKeyPair:
    """An SSH key pair generated for a test VM."""

    private_key: Path
    public_key: Path
    public_key_text: str


@dataclass(frozen=True)
class CloudInitConfig:
    """Configuration rendered into cloud-init user-data and meta-data."""

    hostname: str
    username: str
    ssh_authorized_key: str
    instance_id: str | None = None
    packages: tuple[str, ...] = ()
    runcmd: tuple[str, ...] = ()
    disable_root: bool = True
    ssh_pwauth: bool = False
    sudo_rule: str = "ALL=(ALL) NOPASSWD:ALL"
    groups: tuple[str, ...] = ("wheel",)


@dataclass(frozen=True)
class CloudInitDrive:
    """Paths created for a cloud-init NoCloud seed drive."""

    directory: Path
    user_data_path: Path
    meta_data_path: Path
    iso_path: Path


def generate_ssh_key_pair(directory: Path, *, name: str = "id_ed25519") -> SshKeyPair:
    """Generate an unencrypted Ed25519 key pair for a test VM."""

    directory.mkdir(parents=True, exist_ok=True)
    private_key = directory / name
    if private_key.exists():
        raise FileExistsError(private_key)

    run(
        [
            "ssh-keygen",
            "-t",
            "ed25519",
            "-N",
            "",
            "-f",
            str(private_key),
        ],
    )

    public_key = private_key.with_suffix(".pub")
    return SshKeyPair(
        private_key=private_key,
        public_key=public_key,
        public_key_text=public_key.read_text(encoding="utf-8").strip(),
    )


def create_cloud_init_drive(directory: Path, config: CloudInitConfig) -> CloudInitDrive:
    """Create a NoCloud seed ISO using cloud-localds."""

    directory.mkdir(parents=True, exist_ok=True)
    user_data_path = directory / "user-data"
    meta_data_path = directory / "meta-data"
    iso_path = directory / "seed.iso"

    user_data_path.write_text(__render_user_data(config), encoding="utf-8")
    meta_data_path.write_text(__render_meta_data(config), encoding="utf-8")

    run(["cloud-localds", str(iso_path), str(user_data_path), str(meta_data_path)])
    iso_path.chmod(0o644)

    return CloudInitDrive(
        directory=directory,
        user_data_path=user_data_path,
        meta_data_path=meta_data_path,
        iso_path=iso_path,
    )


def __render_user_data(config: CloudInitConfig) -> str:
    lines = [
        "#cloud-config",
        f"hostname: {json.dumps(config.hostname)}",
        f"disable_root: {json.dumps(config.disable_root)}",
        f"ssh_pwauth: {json.dumps(config.ssh_pwauth)}",
        "users:",
        "  - default",
        f"  - name: {json.dumps(config.username)}",
        f"    groups: {json.dumps(list(config.groups))}",
        f"    sudo: {json.dumps(config.sudo_rule)}",
        "    shell: /bin/bash",
        "    lock_passwd: true",
        "    ssh_authorized_keys:",
        f"      - {json.dumps(config.ssh_authorized_key)}",
    ]

    if config.packages:
        lines.extend(["package_update: true", "packages:"])
        lines.extend(f"  - {json.dumps(package)}" for package in config.packages)

    if config.runcmd:
        lines.append("runcmd:")
        lines.extend(f"  - {json.dumps(command)}" for command in config.runcmd)

    return "\n".join(lines) + "\n"


def __render_meta_data(config: CloudInitConfig) -> str:
    instance_id = config.instance_id or config.hostname
    return (
        f"instance-id: {json.dumps(instance_id)}\n"
        f"local-hostname: {json.dumps(config.hostname)}\n"
    )

"""Live integration coverage for the cowsay proof-of-concept module."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from hyperscaler_testing_core import (
    CloudImage,
    CloudInitConfig,
    LibvirtVm,
    LibvirtVmConfig,
    PyinfraTarget,
    create_cloud_init_drive,
    create_libvirt_workspace,
    create_qcow2_image_from_base,
    download_cloud_image,
    generate_ssh_key_pair,
    missing_commands,
    run_pyinfra,
    run_ssh,
    unique_test_name,
    wait_for_ssh,
    write_ssh_inventory,
)

ROCKY_10_IMAGE_URL = os.environ.get(
    "HYPERSCALER_ROCKY_10_IMAGE_URL",
    "https://dl.rockylinux.org/pub/rocky/10/images/x86_64/"
    "Rocky-10-GenericCloud-Base.latest.x86_64.qcow2",
)

pytestmark = pytest.mark.integration


def test_hyperscaler_poc_installs_cowsay_on_rocky_10(tmp_path: Path) -> None:
    if os.environ.get("HYPERSCALER_RUN_INTEGRATION") != "1":
        pytest.skip("set HYPERSCALER_RUN_INTEGRATION=1 to run live libvirt tests")

    missing = missing_commands(
        "cloud-localds",
        "pyinfra",
        "qemu-img",
        "ssh",
        "ssh-keygen",
    )
    if missing:
        pytest.skip(f"missing required integration commands: {', '.join(missing)}")

    vm_name = unique_test_name("hyperscaler-poc")
    key_pair = generate_ssh_key_pair(tmp_path)
    workspace = create_libvirt_workspace(
        vm_name,
        base_dir=Path(
            os.environ.get(
                "HYPERSCALER_LIBVIRT_WORKSPACE",
                "/var/tmp/hyperscaler-integration",
            ),
        ),
    )

    image = download_cloud_image(
        CloudImage(
            name="rocky-10-genericcloud-base",
            url=ROCKY_10_IMAGE_URL,
        ),
    )
    disk_image = workspace.path / "rocky-10.qcow2"
    create_qcow2_image_from_base(image, disk_image, size_gib=20)

    cloud_init = create_cloud_init_drive(
        workspace.path / "cloud-init",
        CloudInitConfig(
            hostname=vm_name,
            username="hyperscaler",
            ssh_authorized_key=key_pair.public_key_text,
        ),
    )

    vm = LibvirtVm(
        LibvirtVmConfig(
            name=vm_name,
            disk_image=disk_image,
            cloud_init_iso=cloud_init.iso_path,
            uri=os.environ.get("HYPERSCALER_LIBVIRT_URI", "qemu:///system"),
            machine="q35",
            firmware="efi",
        ),
    )

    try:
        vm.define()
        vm.start()

        host = vm.wait_for_ipv4(timeout_seconds=180)
        wait_for_ssh(
            host,
            username="hyperscaler",
            private_key=key_pair.private_key,
            timeout_seconds=240,
        )

        inventory_path = write_ssh_inventory(
            tmp_path / "inventory.py",
            PyinfraTarget(
                name="rocky10",
                host=host,
                user="hyperscaler",
                ssh_key=key_pair.private_key,
            ),
        )
        deploy_path = Path(__file__).resolve().parents[1] / "hyperscaler_poc" / "deploy.py"

        run_pyinfra(inventory_path, deploy_path)

        result = run_ssh(
            host,
            username="hyperscaler",
            private_key=key_pair.private_key,
            command="cowsay hyperscaler",
        )
        assert "hyperscaler" in result.stdout
    finally:
        vm.destroy()
        workspace.cleanup()

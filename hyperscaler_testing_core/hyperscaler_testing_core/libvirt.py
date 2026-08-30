"""libvirt VM lifecycle helpers for integration tests."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
from pathlib import Path
import shutil
import time
from typing import Any
import xml.etree.ElementTree as ET

import libvirt

from hyperscaler_testing_core.commands import run


@dataclass(frozen=True)
class LibvirtVmConfig:
    """Configuration for an ephemeral libvirt VM."""

    name: str
    disk_image: Path
    cloud_init_iso: Path
    uri: str = "qemu:///system"
    network: str = "default"
    memory_mib: int = 2048
    vcpus: int = 2
    arch: str = "x86_64"
    machine: str | None = None
    firmware: str | None = None
    emulator: Path | None = None
    mac_address: str | None = None


@dataclass(frozen=True)
class LibvirtWorkspace:
    """A filesystem workspace suitable for system libvirt QEMU processes."""

    path: Path

    def cleanup(self) -> None:
        """Remove the workspace and its contents."""

        shutil.rmtree(self.path, ignore_errors=True)


class LibvirtVm:
    """Manage a single libvirt VM domain."""

    def __init__(self, config: LibvirtVmConfig) -> None:
        self.config = config

    def define(self) -> None:
        """Define the VM domain in libvirt."""

        with self.__connect() as connection:
            connection.defineXML(self.__render_domain_xml())

    def start(self) -> None:
        """Start the VM domain."""

        with self.__connect() as connection:
            domain = self.__lookup_domain(connection)
            if domain is None:
                raise RuntimeError(f"libvirt domain is not defined: {self.config.name}")
            if not domain.isActive():
                domain.create()

    def destroy(self) -> None:
        """Stop and undefine the VM domain if it still exists."""

        with self.__connect() as connection:
            domain = self.__lookup_domain(connection)
            if domain is None:
                return

            if domain.isActive():
                domain.destroy()

            try:
                domain.undefineFlags(libvirt.VIR_DOMAIN_UNDEFINE_NVRAM)
            except libvirt.libvirtError:
                domain.undefine()

    def wait_for_ipv4(self, *, timeout_seconds: float = 180) -> str:
        """Wait for libvirt DHCP leases to expose a VM IPv4 address."""

        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            address = self.__current_ipv4()
            if address is not None:
                return address
            time.sleep(2)

        raise TimeoutError(f"{self.config.name} did not receive an IPv4 address")

    def __current_ipv4(self) -> str | None:
        with self.__connect() as connection:
            domain = self.__lookup_domain(connection)
            if domain is not None:
                address = self.__domain_ipv4_from_leases(domain)
                if address is not None:
                    return address

            network = self.__lookup_network(connection)
            if network is None:
                return None

            return self.__network_ipv4_from_leases(network)

    def __render_domain_xml(self) -> str:
        domain = ET.Element("domain", {"type": "kvm"})
        ET.SubElement(domain, "name").text = self.config.name
        ET.SubElement(domain, "memory", {"unit": "MiB"}).text = str(self.config.memory_mib)
        ET.SubElement(domain, "vcpu", {"placement": "static"}).text = str(self.config.vcpus)

        os_attrs = {}
        if self.config.firmware is not None:
            os_attrs["firmware"] = self.config.firmware

        os_element = ET.SubElement(domain, "os", os_attrs)
        type_attrs = {"arch": self.config.arch}
        if self.config.machine is not None:
            type_attrs["machine"] = self.config.machine

        ET.SubElement(os_element, "type", type_attrs).text = "hvm"
        ET.SubElement(os_element, "boot", {"dev": "hd"})

        features = ET.SubElement(domain, "features")
        ET.SubElement(features, "acpi")
        ET.SubElement(features, "apic")

        ET.SubElement(domain, "cpu", {"mode": "host-model", "check": "partial"})
        ET.SubElement(domain, "clock", {"offset": "utc"})
        ET.SubElement(domain, "on_poweroff").text = "destroy"
        ET.SubElement(domain, "on_reboot").text = "restart"
        ET.SubElement(domain, "on_crash").text = "destroy"

        devices = ET.SubElement(domain, "devices")
        if self.config.emulator is not None:
            ET.SubElement(devices, "emulator").text = str(self.config.emulator)

        disk = ET.SubElement(devices, "disk", {"type": "file", "device": "disk"})
        ET.SubElement(disk, "driver", {"name": "qemu", "type": "qcow2"})
        ET.SubElement(disk, "source", {"file": str(self.config.disk_image)})
        ET.SubElement(disk, "target", {"dev": "vda", "bus": "virtio"})

        seed = ET.SubElement(devices, "disk", {"type": "file", "device": "cdrom"})
        ET.SubElement(seed, "driver", {"name": "qemu", "type": "raw"})
        ET.SubElement(seed, "source", {"file": str(self.config.cloud_init_iso)})
        ET.SubElement(seed, "target", {"dev": "sda", "bus": "sata"})
        ET.SubElement(seed, "readonly")

        interface = ET.SubElement(devices, "interface", {"type": "network"})
        ET.SubElement(interface, "mac", {"address": self.__mac_address()})
        ET.SubElement(interface, "source", {"network": self.config.network})
        ET.SubElement(interface, "model", {"type": "virtio"})

        serial = ET.SubElement(devices, "serial", {"type": "pty"})
        ET.SubElement(serial, "target", {"port": "0"})
        console = ET.SubElement(devices, "console", {"type": "pty"})
        ET.SubElement(console, "target", {"type": "serial", "port": "0"})

        rng = ET.SubElement(devices, "rng", {"model": "virtio"})
        ET.SubElement(rng, "backend", {"model": "random"}).text = "/dev/urandom"

        ET.indent(domain)
        return ET.tostring(domain, encoding="unicode") + "\n"

    def __mac_address(self) -> str:
        if self.config.mac_address is not None:
            return self.config.mac_address

        digest = hashlib.sha256(self.config.name.encode("utf-8")).digest()
        return "52:54:00:{:02x}:{:02x}:{:02x}".format(
            digest[0],
            digest[1],
            digest[2],
        )

    @contextmanager
    def __connect(self) -> Iterator[Any]:
        connection = libvirt.open(self.config.uri)
        if connection is None:
            raise RuntimeError(f"failed to open libvirt connection: {self.config.uri}")

        try:
            yield connection
        finally:
            connection.close()

    def __lookup_domain(self, connection: Any) -> Any | None:
        try:
            return connection.lookupByName(self.config.name)
        except libvirt.libvirtError:
            return None

    def __lookup_network(self, connection: Any) -> Any | None:
        try:
            return connection.networkLookupByName(self.config.network)
        except libvirt.libvirtError:
            return None

    def __domain_ipv4_from_leases(self, domain: Any) -> str | None:
        try:
            interfaces = domain.interfaceAddresses(
                libvirt.VIR_DOMAIN_INTERFACE_ADDRESSES_SRC_LEASE,
                0,
            )
        except libvirt.libvirtError:
            return None

        wanted_mac = self.__mac_address().lower()
        for interface in interfaces.values():
            if interface.get("hwaddr", "").lower() != wanted_mac:
                continue

            for address in interface.get("addrs", []):
                ip_address = address.get("addr")
                if self.__is_ipv4_address(ip_address):
                    return ip_address

        return None

    def __network_ipv4_from_leases(self, network: Any) -> str | None:
        try:
            leases = network.DHCPLeases(self.__mac_address())
        except libvirt.libvirtError:
            return None

        for lease in leases:
            ip_address = lease.get("ipaddr")
            if self.__is_ipv4_address(ip_address):
                return ip_address

        return None

    @staticmethod
    def __is_ipv4_address(address: object) -> bool:
        if not isinstance(address, str):
            return False

        parts = address.split(".")
        if len(parts) != 4:
            return False

        try:
            return all(0 <= int(part) <= 255 for part in parts)
        except ValueError:
            return False


def create_qcow2_overlay(base_image: Path, output_path: Path, *, size_gib: int = 20) -> Path:
    """Create a qcow2 overlay backed by a cached cloud image."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        raise FileExistsError(output_path)

    run(
        [
            "qemu-img",
            "create",
            "-f",
            "qcow2",
            "-F",
            "qcow2",
            "-b",
            str(base_image.resolve()),
            str(output_path),
            f"{size_gib}G",
        ],
    )
    output_path.chmod(0o666)
    base_image.chmod(0o644)
    return output_path


def create_qcow2_image_from_base(
    base_image: Path,
    output_path: Path,
    *,
    size_gib: int = 20,
) -> Path:
    """Create a standalone qcow2 image from a cloud image."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        raise FileExistsError(output_path)

    run(["qemu-img", "convert", "-O", "qcow2", str(base_image), str(output_path)])
    run(["qemu-img", "resize", str(output_path), f"{size_gib}G"])
    output_path.chmod(0o666)
    return output_path


def create_libvirt_workspace(
    name: str,
    *,
    base_dir: Path | None = None,
) -> LibvirtWorkspace:
    """Create a test workspace that system libvirt can traverse."""

    root = base_dir or Path("/var/tmp/hyperscaler-integration")
    path = root / name
    path.mkdir(parents=True, exist_ok=False)
    root.chmod(0o755)
    path.chmod(0o755)
    return LibvirtWorkspace(path=path)

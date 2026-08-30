"""Install cowsay on DNF-based inventory hosts."""

from pyinfra.operations import dnf, server

DNF_PLUGINS_PACKAGE = "dnf-plugins-core"
EPEL_RELEASE_PACKAGE = "epel-release"
COWSAY_PACKAGE = "cowsay"

dnf.packages(
    name="Install DNF plugin support",
    packages=[DNF_PLUGINS_PACKAGE],
    _sudo=True,
)

server.shell(
    name="Enable CRB repository for EPEL dependencies",
    commands=[
        "dnf repolist --enabled | awk '{print $1}' | grep -qx crb "
        "|| dnf config-manager --set-enabled crb",
    ],
    _sudo=True,
)

dnf.packages(
    name="Enable EPEL repository",
    packages=[EPEL_RELEASE_PACKAGE],
    _sudo=True,
)

dnf.packages(
    name="Install cowsay",
    packages=[COWSAY_PACKAGE],
    _sudo=True,
)

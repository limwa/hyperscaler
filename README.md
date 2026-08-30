# hyperscaler

hyperscaler is a collection of pyinfra modules and inventory files to manage the
infrastructure for my personal VPS and Kubernetes cluster.

## Development Environment

This repository is intended to be used through its Nix development shell:

```sh
direnv allow
direnv exec . python --version
```

The shell includes pyinfra, pytest, cloud image tooling, QEMU, the libvirt
Python bindings, and OpenSSH.

## Applying `hyperscaler_poc`

`hyperscaler_poc` is a small pyinfra module that configures a DNF-based host for
EPEL and installs `cowsay`.

Create a pyinfra inventory for the machine you want to manage:

```python
# inventory.py
hosts = (
    ["192.0.2.10"],
    {
        "ssh_user": "rocky",
        "ssh_key": "/home/me/.ssh/id_ed25519",
        "ssh_strict_host_key_checking": "accept-new",
    },
)
```

The target user must be able to run passwordless sudo, because the module uses
DNF to enable repositories and install packages.

Apply the module with:

```sh
direnv exec . pyinfra inventory.py hyperscaler_poc/hyperscaler_poc/deploy.py --yes
```

Verify the result:

```sh
direnv exec . pyinfra inventory.py exec -- cowsay "hyperscaler"
```

## Integration Tests

Live integration tests for `hyperscaler_poc` live in
`hyperscaler_poc/integration_tests`. They boot a Rocky Linux 10 Generic Cloud
image under QEMU/libvirt, initialize it with cloud-init, apply the pyinfra
module, and assert that `cowsay` runs on the VM.

The reusable VM and isolation helpers live in `hyperscaler_testing_core` so other
modules can use the same testing infrastructure.

The tests are opt-in because they download a cloud image and create live libvirt
domains. A normal run skips them:

```sh
direnv exec . pytest hyperscaler_poc/integration_tests
```

To run the live test:

```sh
HYPERSCALER_RUN_INTEGRATION=1 \
  direnv exec . pytest hyperscaler_poc/integration_tests -m integration -s
```

Prerequisites:

- The current user can access the configured libvirt URI.
- The libvirt `default` network exists and provides DHCP.
- The host has enough disk and memory for a Rocky Linux 10 VM.

Useful environment variables:

- `HYPERSCALER_LIBVIRT_URI`: libvirt URI, default `qemu:///system`.
- `HYPERSCALER_LIBVIRT_WORKSPACE`: libvirt-accessible workspace for temporary VM
  disks and seed images, default `/var/tmp/hyperscaler-integration`.
- `HYPERSCALER_IMAGE_CACHE`: cloud image cache directory, default
  `$XDG_CACHE_HOME/hyperscaler/images` or `~/.cache/hyperscaler/images`.
- `HYPERSCALER_ROCKY_10_IMAGE_URL`: override the Rocky Linux 10 cloud image URL.

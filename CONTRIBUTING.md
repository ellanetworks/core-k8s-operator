# Contributing

To make contributions to this charm, you'll need a working Juju development setup.

## Prerequisites

Install Charmcraft and LXD:
```shell
sudo snap install --classic charmcraft
sudo snap install lxd
sudo adduser $USER lxd
newgrp lxd
lxd init --auto
```

Install Canonical Kubernetes and Multus:
```shell
sudo snap install k8s --classic --channel=1.32-classic/stable
sudo k8s bootstrap
sudo k8s kubectl apply -f https://raw.githubusercontent.com/k8snetworkplumbingwg/multus-cni/master/deployments/multus-daemonset-thick.yml
```

Install Juju and bootstrap a Juju controller

```bash
sudo snap install juju --channel=3/stable
juju add-k8s k8s-localhost
juju bootstrap k8s-localhost
```

This project uses `uv`. You can install it on Ubuntu with:

```shell
sudo snap install --classic astral-uv
```

You can create an environment for development with `uv`:

```shell
uv sync
source .venv/bin/activate
```

## Testing

This project uses `tox` for managing test environments. It can be installed
with:

```shell
uv tool install tox --with tox-uv
```

There are some pre-configured environments
that can be used for linting and formatting code when you're preparing contributions to the charm:

```shell
tox -e lint                                             # code style
tox -e static                                           # static analysis
tox -e unit                                             # unit tests
tox -e integration -- --charm_path=PATH_TO_BUILD_CHARM  # integration tests
```

```note
Integration tests require the charm to be built with `charmcraft pack` first.
```

## Build

Go to the charm directory and run:
```bash
charmcraft pack
```

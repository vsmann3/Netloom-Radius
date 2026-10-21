# Proxmox lab VM

## Initial guest

| Setting | Recommendation |
| --- | --- |
| Name | netloom-radius-lab |
| Installer | Ubuntu Server 24.04 LTS amd64, minimal installation; 26.04 LTS is also supported |
| CPU | 1 socket, 4 cores; host CPU type for a single-host lab |
| Memory | 8 GB; avoid host memory overcommit during measurements |
| Disk | 100 GB SSD-backed storage, VirtIO SCSI controller |
| Network | One VirtIO NIC on a bridge reachable from the test MikroTik |
| OS packages | Minimal installation, SSH server, QEMU guest agent; no desktop |
| Address | Static IP or DHCP reservation, with working DNS and time synchronization |
| Access | Named sudo user with SSH key authentication |

Use a CPU type compatible with all target hosts if live migration is required. Install and enable the QEMU guest agent inside Ubuntu and enable its Proxmox VM option.

This is a starting allocation for the control plane and approximately 500 subscribers. It is not a measured capacity guarantee. The VM does not carry subscriber internet traffic. A future Accel-PPP BNG needs its own network, throughput and CPU sizing.

## Network preparation

- Put management access on a trusted LAN or management VPN.
- Permit SSH only from administrators.
- Permit UDP 1812 and 1813 only from explicitly registered NAS addresses.
- Permit outbound UDP 3799 to registered NAS devices for Disconnect/CoA, including return traffic.
- Keep MariaDB private to the application network; do not publish port 3306 to the LAN.
- Keep the initial panel on the management network; configure HTTPS before credentials are used through a browser.
- Check firewall enforcement at Proxmox, guest and container layers. Container port publishing must be tested from an unauthorized host.
- Use stable NAS source addresses. Do not place different tenants behind an indistinguishable shared RADIUS source address without designing a trusted tenant identification mechanism.

No direct public exposure or router configuration changes are needed to install Ubuntu.

## Information needed for deployment

The user supplied panel hostname `radius.netnoc.in` and VM/public SSH address
`103.215.107.180`. The user reports that DNS points to this address. The installed
Ubuntu version, SSH username/port and key-enrollment method still need confirmation.
See [the deployment target](deployment-target.md).

Record the VM IP, subnet/gateway, management network, MikroTik management/source IP and RouterOS version. Provide the SSH username and public-key enrollment method; do not paste private keys into chat or Git.

Take a baseline snapshot after OS setup. Snapshots help lab rollback; tested database backups are separately required for operational data.

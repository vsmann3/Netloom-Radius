# Netloom deployment target

User-supplied deployment details, recorded 2026-10-21:

| Setting | Value |
| --- | --- |
| Web panel hostname | `radius.netnoc.in` |
| Intended panel URL | `https://radius.netnoc.in` |
| VM/public SSH address | `103.215.107.180` |
| Separate staging VM | `103.215.107.181` |
| Proposed staging hostname | `staging-radius.netnoc.in`, DNS pending confirmation |
| Public source repository | `https://github.com/vsmann3/Netloom-Radius` |
| Preferred host OS | Ubuntu Server LTS; installed release pending confirmation |
| SSH username and port | Pending |
| SSH key enrollment | Pending |

The user reports DNS is pointed at the VM. DNS reachability, SSH access and HTTPS
have not yet been verified. No remote deployment or VM configuration changes have
been performed.

The user requires staging on its own VM, never on the production VM. Point the
staging hostname to `103.215.107.181`. SSH username/port, key enrollment and the
installed Ubuntu release are needed for each host independently.

`deploy/panel.env.example` contains the hostname, HTTPS CSRF origin and secure
cookie settings for the eventual panel deployment. TLS termination still needs
configuration and validation. Compose currently publishes web only on guest
loopback; do not treat these environment settings as an HTTPS proxy.

Use `scripts/prepare-linux.sh` for supported Ubuntu 24.04/26.04 LTS hosts. It also
retains Debian 13 support. The host OS does not change the pinned service images.
Keep database access internal and RADIUS traffic limited to registered NAS
addresses when listeners are enabled. Management access restrictions will be
configured with the HTTPS deployment.

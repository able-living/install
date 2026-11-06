# Odoo Stack Installer Path Compatibility

## Versions

| Launcher release | Installer path behavior |
| --- | --- |
| `v0.1.0-rc.2` | Downloads `deploy/bootstrap/install.sh` |
| `v0.1.0-rc.3` | Downloads `deploy/bootstrap/install.sh` |
| `v0.1.0-rc.4` and later | Prefers `platform/deploy/bootstrap/install.sh`, with an explicit-404 fallback to `deploy/bootstrap/install.sh` |

`v0.1.0-rc.4` is the compatibility release. The two legacy launcher versions
remain supported while the private repository retains its root-level legacy
installer entry.

## Fallback Contract

The launcher resolves the selected ref exactly once. It checks the canonical
path first and falls back only when GitHub explicitly returns HTTP 404 for that
path at the resolved commit. The fallback uses the same 40-character commit SHA.

The launcher stops without fallback on authentication, permission, rate-limit,
network, server, empty-download, or Bash-validation failures. A failed download
from an existing canonical path also does not retry the legacy path.

## Removal Condition

The private repository may remove `deploy/bootstrap/install.sh` only after:

- `v0.1.0-rc.2` and `v0.1.0-rc.3` are no longer supported;
- a launcher release using the canonical-first behavior is the minimum
  supported launcher version;
- the four launcher/installer compatibility combinations have passed against
  both the last pre-move installer SHA and the first post-move installer SHA;
- the private repository records the final matrix and removal result.

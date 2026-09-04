# Able Living Installers

Public, versioned entrypoints for installing Able Living software. This
repository contains installer delivery assets only; application source code,
credentials, and customer data remain private.

## Odoo Stack

Install the latest Production-approved installer:

```bash
bash <(curl -fsSL https://github.com/able-living/install/releases/latest/download/odoo-stack)
```

The launcher downloads the versioned installer payload from the same GitHub
Release, verifies its SHA-256 digest, and then runs it as root. The installer
will ask the operator to authenticate to the private `able-living/odoo-stack`
repository before it downloads any private source.

For reproducible provisioning, replace `latest` with a specific release tag.
Staging candidates are published as prereleases and never replace the latest
Production-approved release.

## Trust Boundary

- Release assets contain no credentials or private Odoo modules.
- Production releases are published only from `able-living/odoo-stack@main`.
- Staging releases are marked as prereleases.
- Every launcher pins and verifies the installer payload checksum before
  execution.

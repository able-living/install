# Able Living Installers

Public, versioned entrypoints for installing Able Living software. This
repository contains launcher code only; application source code, credentials,
and customer data remain private.

## Odoo Stack

Install with the latest Production-approved launcher:

```bash
bash <(curl -fsSL https://github.com/able-living/install/releases/latest/download/odoo-stack)
```

The launcher installs GitHub CLI when needed, asks the operator to authenticate,
verifies access to the private `able-living/odoo-stack` repository, resolves the
requested installer ref to a full Git SHA, and downloads the real installer from
that exact SHA. It then passes the temporary credential file to the installer
without placing a token in command-line arguments.

The default private installer ref is `main`. An approved Staging test can select
another long-lived branch or an exact commit without changing the public
launcher:

```bash
ABLE_LIVING_INSTALLER_REF=staging \
  bash <(curl -fsSL https://github.com/able-living/install/releases/latest/download/odoo-stack)
```

For reproducible provisioning, replace `latest` with a specific launcher release
tag and set `ABLE_LIVING_INSTALLER_REF` to a full 40-character Git SHA.

## Trust Boundary

- The public launcher contains no credentials or private Odoo modules.
- Private source is downloaded only after repository permission is verified.
- The installer ref is resolved once and downloaded from that exact commit.
- Temporary source and credential files are removed when the launcher exits.

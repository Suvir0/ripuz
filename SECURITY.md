# Security Policy

## Supported versions

Only the latest `main` branch is supported.

## Reporting a vulnerability

Please **do not** open public issues for sensitive security reports. Use GitHub Security Advisories to report privately:

https://github.com/Suvir0/ripuz/security/advisories

If the issue is not sensitive, a standard GitHub issue is fine.

## Safe deployment guidance

Ripuz is intended for trusted networks. If you expose the Web UI outside your LAN, set `RIPUZ_AUTH_PASS` (and optionally `RIPUZ_AUTH_USER`) and place it behind a reverse proxy, VPN, or firewall.

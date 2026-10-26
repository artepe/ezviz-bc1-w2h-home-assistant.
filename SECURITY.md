# Security policy

## Reporting a vulnerability

Please do not report security problems in public issues. Use GitHub's private vulnerability reporting (**Security → Report a vulnerability** on this repository) or contact the maintainer privately through the GitHub profile [@artepe](https://github.com/artepe). Please allow time for a fix before publishing details.

## Supported versions

Security fixes are made to the latest release and the `main` branch only.

## Security design

- The camera manager accepts connections only from the Home Assistant ingress proxy (`172.30.32.2`) and is an admin-only panel; every change needs a per-start CSRF token and a JSON body of at most 32 KB.
- Responses carry a strict Content-Security-Policy, `nosniff`, `no-store` and `same-origin` referrer policy. Errors shown in the UI are fixed texts, never raw upstream output that could contain session tokens.
- Camera proxies listen on `127.0.0.1` only. The EZVIZ session token is kept in private add-on storage (`/data`, mode 0600); the account password stays in the add-on options.

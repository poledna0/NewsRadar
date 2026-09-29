# Security Policy

## Supported Versions

The supported version is the `main` branch. Security fixes are published to this branch; update the Docker image after a security fix is released.

## Reporting a Vulnerability

Do not disclose exploitable details in a public issue. Use GitHub's **Report a vulnerability** feature under the **Security** tab to privately notify the maintainers. Include reproduction steps, impact, affected version/commit, and a suggested fix, if available.

If the private reporting feature is not enabled for the repository, open an issue without exploitable details and request a private communication channel. Do not include passwords, tokens, or user data.

## Security Scope

The following areas are particularly security-sensitive:

- SSRF/DNS rebinding in the scraper
- Cloudflare Access JWT validation
- Origin exposure without authentication
- XSS/CSRF
- Request rate limits
- Ollama prompts and results
- SQLite migrations

NewsRadar does not replace network-level access controls. Keep the origin inaccessible from the public internet. Cloudflare Access only protects the origin when direct traffic to the origin is also restricted, or when the application validates the configured JWT.
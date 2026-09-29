# Contributing

Thank you for considering contributing to NewsRadar. The project prioritizes operational simplicity, privacy, and local execution.

## Before You Start

1. Check existing issues to avoid duplicate work.
2. For major changes, open an issue describing the problem and the proposed solution.
3. Do not include tokens, private URLs, personal data, or production databases in commits.

## Development Environment

Requirements: Python 3.12+ and, optionally, Docker Compose.

```sh
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
python -m pytest -q
```

Tests should be deterministic: mock HTTP, SearXNG, and Ollama instead of relying on external services.

## Guidelines

- Keep FastAPI, Jinja, and JavaScript lightweight; do not introduce a heavy frontend without a clear need.
- Validate external data and keep SearXNG/Ollama as configurable infrastructure.
- Preserve existing data: schema changes must use additive migrations and include tests.
- Treat RSS, scraping, and LLM results as untrusted input.
- Prefer short comments that explain non-obvious security decisions or control flow.
- Update the README or `docs/` when changing installation, configuration, or API behavior.

## Pull Requests

- Keep one focused change per PR, with context and expected behavior.
- Include tests for new code paths or bug fixes.
- Run `python -m pytest -q` and describe the result.
- Use Conventional Commits with a concise description in English, for example `feat: add source filter` or `fix: validate redirect target`.
- Do not include generated files, `.env` files, SQLite databases, or credentials.

## Review

PRs are reviewed for security, self-hosting compatibility, readability, testing, and data preservation. A contribution may be requested to be split into smaller changes before it is accepted.git 
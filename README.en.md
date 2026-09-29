# NewsRadar

**Your self-hosted radar for news and research.** Discover, deduplicate and summarize sources around your interests with SearXNG, RSS and local Ollama.

[Português](README.md) · [English](README.en.md)

[![CI](https://github.com/poledna0/NewsRadar/actions/workflows/tests.yml/badge.svg)](https://github.com/poledna0/NewsRadar/actions/workflows/tests.yml)
[![Apache 2.0 License](https://img.shields.io/badge/license-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Docker Compose](https://img.shields.io/badge/Docker-Compose-2496ED.svg?logo=docker&logoColor=white)](docker-compose.yml)

NewsRadar is a self-hosted news aggregator: define interests, not hundreds of websites. It discovers news and research, stores articles in SQLite, and uses a locally hosted model for classification, grouping and Portuguese summaries.

> **Status:** actively developed. AI classifications and summaries may be wrong; always check the original source.

## Why NewsRadar?

- **Automatic discovery:** topic searches through SearXNG, complemented by RSS/Atom feeds.
- **Research separated from news:** papers/preprints and journalism have distinct filters.
- **Fewer duplicates:** URLs and similar headlines are checked before using AI.
- **Local AI:** Ollama handles classification and summaries without a paid AI API.
- **Your data stays yours:** SQLite persists on your host; configuration is plain YAML.
- **Lightweight UI:** FastAPI, Jinja and simple JavaScript, with no heavy frontend framework.

## Quick start

Requirements: Docker Engine with Compose v2, an accessible SearXNG instance and Ollama.

```sh
git clone https://github.com/poledna0/NewsRadar.git
cd NewsRadar
cp .env.example .env
mkdir -p data
sed -i "s/^APP_UID=.*/APP_UID=$(id -u)/; s/^APP_GID=.*/APP_GID=$(id -g)/" .env
```

Set service URLs reachable **from inside the container** in `.env`. Example for SearXNG and Ollama running on the host:

```dotenv
SEARXNG_URL=http://host.docker.internal:6767
OLLAMA_URL=http://host.docker.internal:11434
ALLOWED_HOSTS=localhost,127.0.0.1,host.docker.internal,SERVER_IP
```

SearXNG must enable its JSON API. See [docs/SEARXNG.md](docs/SEARXNG.md). Pull the configured local model:

```sh
ollama pull qwen3.5:9b
```

Start NewsRadar:

```sh
docker compose up -d --build
```

Open `http://SERVER_IP:8000`. Check the deployment:

```sh
curl http://localhost:8000/health
docker compose logs -f newsradar
```

The SQLite database lives in `./data/newsradar.db`. The container runs without root and with a read-only root filesystem. Compose does not start SearXNG or Ollama and does not modify existing services.

## Add topics

Click **+ Tema** in the UI and enter a name plus optional search queries, one per line. UI-created topics are persisted in SQLite. You can also edit `config.yaml` before startup:

```yaml
languages: [pt, en]
topics:
  - name: cybersecurity
    queries:
      - cybersecurity
      - cyber attack
      - vulnerability CVE
    enabled: true
  - name: artificial intelligence
    queries:
      - artificial intelligence
      - machine learning
    enabled: true
```

Each topic triggers limited news searches and one additional research search. Limits are configurable in `.env`. Add feeds in `sources.yaml`; use `article_type: research` only for primary research/paper sources. The classifier distinguishes original studies from reporting about studies.

## Local AI

Ollama runs separate tasks:

1. Classify relevance, category, topics and type (`news` or `research`).
2. Summarize in Portuguese with neutral language and source attribution.
3. Consolidate similar coverage while preserving source links.
4. Translate text or article summaries from English to Brazilian Portuguese on demand.

If Ollama is unavailable, collection continues and articles remain `pending_ai`. The default model is `qwen3.5:9b`; set `OLLAMA_MODEL` to use another model. LLM output is not an independent factual source.

## API

- `GET /health`: service and database health.
- `GET /api/articles`: filter by `topic`, `kind=news|research`, `hours`, `source`, `search` and `sort`.
- `GET /api/articles/{id}`: article and related sources.
- `GET /api/topics` and `POST /api/topics`: list and add topics.
- `DELETE /api/topics/{id}`: disable a topic without deleting history.
- `POST /api/translate`: translate up to 12,000 characters.
- `POST /api/articles/{id}/translate`: translate and store an article summary.
- `POST /api/collect`: trigger a manual collection.
- `GET /api/stats`: counts and last collection state.

## Documentation

- [Code and security guide](docs/GUIA_DO_CODIGO.txt)
- [SearXNG setup](docs/SEARXNG.md)
- [GitHub launch checklist](docs/PUBLICAR_NO_GITHUB.md)
- [Contributing](CONTRIBUTING.md)
- [Security policy](SECURITY.md)
- [Code of conduct](CODE_OF_CONDUCT.md)

## Security

The origin has **no built-in authentication by default**. The app can verify Cloudflare Access JWTs when `CF_ACCESS_TEAM_DOMAIN` and `CF_ACCESS_AUDIENCE` are configured, but NewsRadar does not configure the proxy. Do not forward the origin port from your router; restrict direct access with a firewall/private network and configure Access before exposing the app.

The scraper validates public destinations at resolution time, pins the IP to the socket and revalidates redirects. The UI uses CSP, TrustedHost, body limits, origin validation and write rate limits. See [SECURITY.md](SECURITY.md) and the code guide for residual risks.

## Tests and contributing

```sh
pip install -r requirements-dev.txt
pytest -q
```

Pull requests and bug reports are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) before contributing. CI runs tests on Python 3.12.

## License

Apache License 2.0. See [LICENSE](LICENSE).

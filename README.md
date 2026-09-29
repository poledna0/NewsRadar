# NewsRadar

**Seu radar de notícias e pesquisas, hospedado por você.** Descubra, deduplique e resuma fontes sobre os seus temas usando SearXNG, RSS e Ollama local.

[Português](README.md) · [English](README.en.md)

[![CI](https://github.com/poledna0/NewsRadar/actions/workflows/tests.yml/badge.svg)](https://github.com/poledna0/NewsRadar/actions/workflows/tests.yml)
[![Licença Apache 2.0](https://img.shields.io/badge/licen%C3%A7a-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Docker Compose](https://img.shields.io/badge/Docker-Compose-2496ED.svg?logo=docker&logoColor=white)](docker-compose.yml)

O NewsRadar é um agregador self-hosted: você define interesses, não centenas de sites. O sistema busca notícias e estudos, guarda os artigos em SQLite e usa um modelo executado localmente para classificação, agrupamento e resumos em português.

> **Status:** em desenvolvimento ativo. A classificação e os resumos são auxiliares e podem conter erros; consulte sempre a fonte original.

## Por que NewsRadar?

- **Descoberta automática:** pesquisas por tema no SearXNG e fontes RSS/Atom complementares.
- **Pesquisa separada de notícia:** papers/preprints e cobertura jornalística têm filtros próprios.
- **Menos duplicatas:** URLs e títulos semelhantes são comparados antes de usar IA.
- **IA local:** classificação e resumos via Ollama, sem API paga de IA.
- **Seus dados ficam seus:** SQLite persistido no host e configuração em YAML.
- **Interface leve:** FastAPI, Jinja e JavaScript simples; sem frontend pesado.

## Início rápido

Requisitos: Docker Engine com Compose v2, uma instância SearXNG e Ollama acessíveis pelo host/container.

```sh
git clone https://github.com/poledna0/NewsRadar.git
cd NewsRadar
cp .env.example .env
mkdir -p data
sed -i "s/^APP_UID=.*/APP_UID=$(id -u)/; s/^APP_GID=.*/APP_GID=$(id -g)/" .env
```

Edite `.env` para informar os endereços alcançáveis **de dentro do container**. Exemplo para SearXNG e Ollama executados no host:

```dotenv
SEARXNG_URL=http://host.docker.internal:6767
OLLAMA_URL=http://host.docker.internal:11434
ALLOWED_HOSTS=localhost,127.0.0.1,host.docker.internal,IP_DO_SERVIDOR
```

O SearXNG precisa permitir a API JSON. Consulte [docs/SEARXNG.md](docs/SEARXNG.md). Baixe o modelo local configurado:

```sh
ollama pull qwen3.5:9b
```

Suba o NewsRadar:

```sh
docker compose up -d --build
```

Acesse `http://IP_DO_SERVIDOR:8000`. Verifique a instalação:

```sh
curl http://localhost:8000/health
docker compose logs -f newsradar
```

`./data` guarda o banco `newsradar.db`. O container roda sem root e com sistema de arquivos raiz somente leitura. O Compose não inicia SearXNG nem Ollama e não altera serviços existentes.

## Configure seus temas

Na interface, clique em **+ Tema**, informe um nome e consultas opcionais, uma por linha. O tema é persistido no SQLite. Também é possível editar `config.yaml` antes de iniciar. Exemplo:

```yaml
languages: [pt, en]
topics:
  - name: cybersecurity
    queries:
      - cybersecurity
      - cyber attack
      - vulnerability CVE
    enabled: true
  - name: inteligência artificial
    queries:
      - artificial intelligence
      - machine learning
    enabled: true
```

Cada tema gera consultas limitadas de notícias e uma busca científica adicional. Os limites ficam em `.env`. Para incluir feeds, edite `sources.yaml`; marque `article_type: research` somente para fontes primárias de papers/preprints. A classificação separa estudos originais de reportagens que apenas falam de estudos.

## O que a IA faz

O Ollama executa tarefas separadas:

1. Classifica relevância, categoria, temas e tipo (`news` ou `research`).
2. Resume o conteúdo em português com instruções de neutralidade e atribuição.
3. Consolida coberturas semelhantes, preservando links das fontes.
4. Traduz texto ou resumos do inglês para pt-BR sob demanda.

Se o Ollama estiver indisponível, a coleta continua e os artigos ficam como `pending_ai`. O modelo padrão é `qwen3.5:9b`; escolha outro em `OLLAMA_MODEL` se preferir. Resultados de LLM nunca devem ser tratados como fonte factual independente.

## API

- `GET /health`: saúde do serviço e banco.
- `GET /api/articles`: filtros por `topic`, `kind=news|research`, `hours`, `source`, `search` e `sort`.
- `GET /api/articles/{id}`: artigo e fontes relacionadas.
- `GET /api/topics` e `POST /api/topics`: listar e adicionar temas.
- `DELETE /api/topics/{id}`: desativar tema; histórico preservado.
- `POST /api/translate`: traduzir até 12 mil caracteres.
- `POST /api/articles/{id}/translate`: traduzir e guardar o resumo do artigo.
- `POST /api/collect`: executar coleta manual.
- `GET /api/stats`: contagens e estado da última coleta.

## Documentação

- [Guia do código e visão de segurança](docs/GUIA_DO_CODIGO.txt)
- [Configurar SearXNG](docs/SEARXNG.md)
- [Preparar a página pública do GitHub](docs/PUBLICAR_NO_GITHUB.md)
- [Contribuir](CONTRIBUTING.md)
- [Política de segurança](SECURITY.md)
- [Código de conduta](CODE_OF_CONDUCT.md)

## Segurança

A origem **não tem autenticação própria por padrão**. O projeto pode validar JWT do Cloudflare Access quando `CF_ACCESS_TEAM_DOMAIN` e `CF_ACCESS_AUDIENCE` são configurados, mas o proxy não é configurado pelo NewsRadar. Não encaminhe a porta da origem pelo roteador; restrinja o acesso direto por firewall/rede e configure o Access antes de expor a aplicação.

O scraper valida destino público em cada resolução, fixa o IP no socket e revalida redirecionamentos. A interface aplica CSP, TrustedHost, limites de corpo, validação de origem e rate limits nas escritas. Veja os limites residuais em [SECURITY.md](SECURITY.md) e no guia de código.

## Testes e contribuição

```sh
pip install -r requirements-dev.txt
pytest -q
```

Pull requests e relatos de bugs são bem-vindos. Leia [CONTRIBUTING.md](CONTRIBUTING.md) antes de abrir uma contribuição. A CI executa os testes em Python 3.12.

## Licença

Apache License 2.0. Veja [LICENSE](LICENSE).

---

**Descrição curta para GitHub:** Self-hosted news and research radar. Discover, deduplicate and summarize stories with SearXNG, RSS and local Ollama.

**Tópicos sugeridos:** `self-hosted` · `news-aggregator` · `rss` · `fastapi` · `ollama` · `local-ai` · `research` · `python`

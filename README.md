# NewsRadar

Agregador pessoal de notícias self-hosted. O NewsRadar descobre matérias por tema usando SearXNG e feeds RSS/Atom, extrai o conteúdo disponível, agrupa manchetes semelhantes e usa um servidor Ollama externo para classificação e resumo em português. O banco SQLite e toda a configuração ficam no servidor do usuário.

## Requisitos

- Docker Engine e Docker Compose v2 para a instalação recomendada.
- Uma instância SearXNG acessível pelo container (opcional; RSS continua funcionando sem ela).
- Ollama acessível pelo container (opcional; artigos permanecem como `pending_ai` quando indisponível).

## Início rápido com Docker

Na pasta do projeto, crie o arquivo de ambiente, prepare o diretório persistente com o UID/GID do usuário e inicie o serviço:

```sh
cp .env.example .env
mkdir -p data
sed -i "s/^APP_UID=.*/APP_UID=$(id -u)/; s/^APP_GID=.*/APP_GID=$(id -g)/" .env
docker compose up -d --build
```

Acesse `http://IP_DO_SERVIDOR:8000`. O banco persiste em `./data/newsradar.db`. Para alterar os temas ou feeds, edite `config.yaml` e `sources.yaml`; os arquivos são montados no container em modo somente leitura e serão lidos na próxima coleta.

O Compose contém somente o NewsRadar. Ollama e SearXNG não são iniciados automaticamente. O valor de exemplo `SEARXNG_URL=http://searxng:8080` pressupõe um SearXNG em uma rede Docker acessível com esse nome. Para uma instalação externa, configure o endereço que o container realmente alcança, por exemplo `http://host.docker.internal:8080` ou o endereço do seu servidor. O SearXNG precisa permitir o formato JSON de sua API de busca. Há um exemplo comentado no `docker-compose.yml` para adicioná-lo depois.

### Ollama

Instale e execute Ollama fora deste Compose. No `.env`, ajuste `OLLAMA_URL` para o endereço alcançável pelo container. Em Docker Desktop, `http://host.docker.internal:11434` costuma apontar para o host; no Linux, o Compose declara o alias `host.docker.internal` via `host-gateway`.

Baixe o modelo configurado:

```sh
ollama pull qwen3.5:9b
```

`qwen3.5:9b` é o padrão para equilibrar qualidade de classificação/resumo e consumo de memória. O modelo é executado localmente pelo Ollama e não exige uma API paga. Ajuste `OLLAMA_MODEL` se preferir outro modelo compatível com a API de geração do Ollama.

## Configuração

### Variáveis de ambiente

As opções de infraestrutura ficam no `.env`; use `.env.example` como base. As principais são:

| Variável | Padrão | Uso |
| --- | --- | --- |
| `APP_PORT` | `8000` | Porta publicada no host |
| `DATABASE_URL` | `sqlite:///./data/newsradar.db` | Banco SQLAlchemy |
| `SEARXNG_URL` | `http://searxng:8080` | URL base da instância de busca |
| `OLLAMA_URL` | `http://host.docker.internal:11434` | URL base do Ollama externo |
| `OLLAMA_MODEL` | `qwen3.5:9b` | Modelo local de IA |
| `COLLECTION_INTERVAL_MINUTES` | `30` | Intervalo mínimo entre coletas agendadas (5 ou mais) |
| `MAX_RESULTS_PER_QUERY` | `10` | Limite de resultados para cada consulta |
| `ARTICLE_MAX_AGE_HOURS` | `48` | Idade máxima de publicação aceita |
| `REQUEST_TIMEOUT_SECONDS` | `15` | Timeout das requisições externas |
| `HTTP_USER_AGENT` | `NewsRadar/0.1 ...` | Identificação das requisições |
| `MAX_QUERIES_PER_TOPIC` | `4` | Limite de consultas por tema em cada ciclo |
| `AI_ARTICLES_PER_RUN` | `200` | Limite de artigos pendentes enviados ao Ollama em cada ciclo |
| `COLLECT_ON_START` | `true` | Faz uma coleta ao iniciar a aplicação |
| `RESPECT_ROBOTS_TXT` | `true` | Consulta robots.txt antes de extrair páginas |

Não coloque credenciais no YAML nem no controle de versão. O `.env` é ignorado pelo Git.

### Temas e idiomas

Edite `config.yaml`; cada tema tem nome, consultas opcionais e opção `enabled`:

```yaml
languages:
  - pt
  - en
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
      - inteligência artificial
    enabled: true
```

Sem consultas explícitas, são usadas o nome do tema e uma variante com `news`. Até `MAX_QUERIES_PER_TOPIC` consultas são enviadas ao SearXNG por tema e ciclo. A lista `languages` documenta os idiomas de interesse; os resultados atuais são coletados sem uma restrição de idioma rígida para não descartar cobertura relevante.

### Feeds RSS/Atom

Edite `sources.yaml` e adicione entradas à lista `feeds`:

```yaml
feeds:
  - name: Blog técnico
    url: https://example.org/feed.xml
    enabled: true
```

Cada feed é isolado: erro de rede, HTTP 403 ou XML inválido é registrado e não interrompe as outras fontes. RSS complementa a busca; não é a única via de descoberta.

## Execução sem Docker

Com Python 3.12 ou superior:

```sh
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Para uso local sem SearXNG, configure outro endereço em `SEARXNG_URL`; falhas de busca não impedem leitura de feeds RSS.

## Uso e API

A página inicial mostra as notícias mais importantes e o fluxo recente, com filtros por tema, período de 6/24 horas, fonte, relevância e palavra. A aba **Múltiplas fontes** reúne matérias com manchetes semelhantes e links para as fontes relacionadas. O botão **Coletar agora** executa o ciclo manual.

- `GET /api/articles`: lista filtrável; parâmetros `topic`, `hours`, `source`, `search`, `sort=date|relevance`, `limit` e `offset`.
- `GET /api/articles/{id}`: detalhes de um artigo.
- `GET /api/topics`: temas ativos/configurados.
- `GET /api/sources`: feeds registrados e domínios descobertos.
- `POST /api/collect`: inicia uma coleta das fontes configuradas somente para clientes da rede privada; retorna HTTP 409 se outra já estiver em andamento.
- `GET /api/stats`: contagens e horário da última coleta.
- `GET /health`: estado da aplicação e do SQLite.

Exemplo de resposta de classificação produzida pelo Ollama:

```json
{
  "relevance_score": 92,
  "category": "cybersecurity",
  "topics": ["cybersecurity", "Linux"],
  "important": true
}
```

O resumo é uma segunda chamada ao modelo, separada da classificação, e solicita 3 a 6 frases factuais em português com atribuição de alegações. Respostas inválidas ou indisponibilidade do Ollama deixam o artigo em `pending_ai`, sem impedir a coleta.

## Pipeline

1. O worker agenda ciclos a cada 30 minutos (configurável) e pode coletar uma vez ao iniciar.
2. Cada tema gera um número limitado de consultas no SearXNG; os feeds configurados são consultados em seguida.
3. URLs HTTP(S) são normalizadas e verificadas contra destinos locais/privados antes de requisições de artigo. URLs canônicas existentes são ignoradas.
4. Títulos recentes são comparados com similaridade convencional. Manchetes semelhantes são agrupadas no registro existente, que mantém links das fontes relacionadas.
5. Trafilatura tenta extrair título, autor, data, descrição, imagem e conteúdo principal, respeitando robots.txt. Metadados da busca/RSS são mantidos se a extração falhar.
6. Artigos novos são salvos no SQLite antes da IA. Classificação e resumo são executados separadamente; erros deixam o artigo pendente e uma coleta posterior tenta processá-lo novamente.

O worker limita cada ciclo; um único feed, artigo ou serviço externo com falha não encerra o ciclo inteiro. Não há migrações automáticas para versões antigas do schema nesta primeira versão; faça backup de `data/` antes de atualizações que alterem modelos.

## Mapa do código

- `app/main.py`: cria a aplicação FastAPI, inicializa o schema SQLite, agenda o worker, aplica filtros da interface e expõe a API. A coleta manual não recebe URL ou comando do cliente e aceita somente conexões de loopback/rede privada.
- `app/config.py`: lê `.env`, `config.yaml` e `sources.yaml`; concentra limites, intervalos e endereços externos.
- `app/database.py` e `app/models.py`: engine/sessões SQLAlchemy e tabelas de artigos, fontes, temas, associações e execuções.
- `app/services/search.py` e `rss.py`: adaptadores independentes para SearXNG e RSS/Atom; erros de cada consulta ou feed são isolados.
- `app/services/http.py`: timeout, retry, validação de destino público e nova validação de cada redirecionamento antes de acessar uma página externa.
- `app/services/extractor.py`: consulta robots.txt e extrai conteúdo/metadados com Trafilatura; falhas resultam em metadados de descoberta, não em perda do artigo.
- `app/services/deduplicator.py`: canonicalização de URLs e comparação convencional de títulos, sem chamada de IA.
- `app/services/ollama.py`: prompts e chamadas separadas de classificação, resumo e consolidação de cobertura multi-fonte.
- `app/services/pipeline.py`: coordena uma execução, persiste resultados antes da IA e deixa itens não processados como `pending_ai`.
- `app/templates/` e `app/static/`: HTML Jinja com escape automático, estilos e interações leves em JavaScript.
- `tests/`: testes das regras de URL/título, integração com serviços simulados, persistência e endpoints.

Para auditar uma alteração, siga a entrada de `collect_news()` até os adaptadores de fonte e `_ingest()`, confira as mutações no modelo `Article` e então examine `_process_pending()` e os prompts de `ollama.py`. O resumo gerado por um LLM não é uma garantia factual; compare com as fontes originais antes de reutilizar informação sensível.

## Logs e manutenção

```sh
docker compose logs -f newsradar
docker compose ps
curl http://localhost:8000/health
curl -X POST http://localhost:8000/api/collect
```

No PowerShell, `Invoke-RestMethod -Method Post http://localhost:8000/api/collect` é uma alternativa ao `curl`. Para parar sem apagar dados, use `docker compose down`; o volume local `./data` permanece no disco.

## Testes

```sh
pytest -q
```

Os testes cobrem normalização e deduplicação, classificação, persistência SQLite, leitura/erro de RSS e health/API. A primeira execução instala as dependências de desenvolvimento com `pip install -r requirements-dev.txt`.

## Segurança e limites

O container roda sem privilégios, com filesystem raiz somente leitura, sem capabilities e com `no-new-privileges`; apenas `./data` é gravável. O endpoint administrativo não recebe URLs nem comandos: opera apenas sobre `config.yaml` e `sources.yaml`, e a coleta manual é restrita a clientes locais/privados. Requisições de scraping bloqueiam destinos privados, loopback, credenciais embutidas e protocolos diferentes de HTTP(S); redirecionamentos passam pela mesma validação. O `.env` não deve ser publicado. Como a API de leitura não tem autenticação, não exponha a porta diretamente à internet; use firewall/rede privada ou um proxy com controles de acesso. Conteúdo de artigos é renderizado pelo Jinja com escape automático. O agregador não tenta contornar bloqueios de scraping; quando o site recusa ou proíbe extração, mantém os dados de descoberta e o link original.
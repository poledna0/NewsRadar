# NewsRadar

Agregador pessoal de notícias self-hosted. O NewsRadar descobre matérias por tema usando SearXNG e feeds RSS/Atom, extrai o conteúdo disponível, agrupa manchetes semelhantes e usa um servidor Ollama externo para classificação e resumo em português. O banco SQLite e toda a configuração ficam no servidor do usuário.

Para uma leitura guiada do fluxo, dos módulos e da revisão de segurança antes de abrir o código, leia [GUIA_DO_CODIGO.txt](GUIA_DO_CODIGO.txt).

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
| `MAX_RESULTS_PER_FEED` | `20` | Limite de entradas lidas de cada feed por ciclo |
| `ARTICLE_MAX_AGE_HOURS` | `48` | Idade máxima de publicação aceita |
| `REQUEST_TIMEOUT_SECONDS` | `15` | Timeout das requisições externas |
| `HTTP_USER_AGENT` | `NewsRadar/0.1 ...` | Identificação das requisições |
| `MAX_QUERIES_PER_TOPIC` | `4` | Limite de consultas por tema em cada ciclo |
| `MAX_RESEARCH_RESULTS_PER_TOPIC` | `5` | Limite adicional de resultados científicos por tema |
| `AI_ARTICLES_PER_RUN` | `200` | Limite de artigos pendentes enviados ao Ollama em cada ciclo |
| `MAX_HTTP_RESPONSE_BYTES` | `8000000` | Tamanho máximo de cada página/feed baixado |
| `MAX_REQUEST_BODY_BYTES` | `64000` | Limite de corpo HTTP aceito |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1,host.docker.internal` | Hosts HTTP permitidos; acrescente IP LAN e domínio do proxy |
| `CF_ACCESS_TEAM_DOMAIN` | vazio | Domínio da equipe Cloudflare Access; habilita validação JWT na origem |
| `CF_ACCESS_AUDIENCE` | vazio | Audience da aplicação Access; use junto com o domínio da equipe |
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

Sem consultas explícitas, é usado o próprio nome do tema. Pela interface, informe sinônimos e consultas em linhas separadas. Cada tema consulta fontes de notícias e faz uma busca científica adicional limitada por `MAX_RESEARCH_RESULTS_PER_TOPIC`. A lista `languages` documenta os idiomas de interesse; os resultados são coletados sem restrição rígida de idioma.

Na página, use **+ Tema** para cadastrar um tema e consultas, e **×** para desativá-lo. Os temas adicionados pela tela ficam no SQLite e sobrevivem a reinícios; temas do YAML continuam compatíveis.

### Feeds RSS/Atom

Edite `sources.yaml` e adicione entradas à lista `feeds`:

```yaml
feeds:
  - name: Blog técnico
    url: https://example.org/feed.xml
    enabled: true
```

Cada feed é isolado: erro de rede, HTTP 403 ou XML inválido é registrado e não interrompe as outras fontes. O arquivo inclui fontes jornalísticas, centros de divulgação científica e feeds primários de preprints arXiv. Marque `article_type: research` somente para fontes primárias; o classificador separa paper/preprint de uma matéria de jornal que apenas relata um estudo.

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

- `GET /api/articles`: lista filtrável; parâmetros `topic`, `kind=news|research`, `hours`, `source`, `search`, `sort=date|relevance`, `limit` e `offset`.
- `GET /api/articles/{id}`: detalhes de um artigo.
- `GET /api/topics`: temas ativos/configurados.
- `POST /api/topics`: adiciona um tema com consultas; `DELETE /api/topics/{id}` desativa sem apagar vínculos históricos.
- `POST /api/translate`: traduz até 12 mil caracteres para pt-BR via Ollama.
- `POST /api/articles/{id}/translate`: traduz e guarda título/resumo para evitar inferência repetida.
- `GET /api/sources`: feeds registrados e domínios descobertos.
- `POST /api/collect`: inicia uma coleta das fontes configuradas somente para clientes da rede privada; retorna HTTP 409 se outra já estiver em andamento.
- `GET /api/stats`: contagens e horário da última coleta.
- `GET /health`: estado da aplicação e do SQLite.

Exemplo de resposta de classificação produzida pelo Ollama:

```json
{
  "relevance_score": 92,
  "category": "cybersecurity",
  "article_type": "news",
  "topics": ["cybersecurity", "Linux"],
  "important": true
}
```

O resumo é uma segunda chamada ao modelo, separada da classificação, e solicita 3 a 6 frases factuais em português com atribuição de alegações. Respostas inválidas ou indisponibilidade do Ollama deixam o artigo em `pending_ai`, sem impedir a coleta.

## Pipeline

1. O worker agenda coletas a cada 30 minutos (configurável) e tenta drenar pendências de IA em lotes menores a cada 5 minutos.
2. Cada tema gera consultas limitadas nas categorias `news` e `science` do SearXNG; os feeds são consultados em seguida.
3. URLs HTTP(S) são normalizadas e verificadas contra destinos locais/privados antes de requisições de artigo. URLs canônicas existentes são ignoradas.
4. Títulos recentes são comparados com similaridade convencional. Manchetes semelhantes são agrupadas no registro existente, que mantém links das fontes relacionadas.
5. Trafilatura tenta extrair título, autor, data, descrição, imagem e conteúdo principal, respeitando robots.txt. Metadados da busca/RSS são mantidos se a extração falhar.
6. Artigos novos são salvos no SQLite antes da IA. A classificação diferencia notícia jornalística de paper/preprint; feeds de fontes primárias informam esse tipo como sugestão. Classificação e resumo são chamadas separadas; erros deixam o artigo pendente.

O worker limita artigos por tema, consulta e feed; uma única fonte com erro não encerra o ciclo. O startup faz migrações SQLite aditivas para novas colunas, mas não remove colunas antigas nem oferece rollback automático; mantenha backup de `data/` antes de atualizar.

## Mapa do código

- `app/main.py`: cria a aplicação FastAPI, inicializa o schema SQLite, agenda o worker, aplica filtros da interface e expõe a API. A coleta manual não recebe URL ou comando do cliente e aceita somente conexões de loopback/rede privada.
- `app/config.py`: lê `.env`, `config.yaml` e `sources.yaml`; concentra limites, intervalos e endereços externos.
- `app/database.py` e `app/models.py`: engine/sessões SQLAlchemy e tabelas de artigos, fontes, temas, associações e execuções.
- `app/services/search.py` e `rss.py`: adaptadores independentes para SearXNG e RSS/Atom; erros de cada consulta ou feed são isolados.
- `app/services/http.py`: timeout, retry, validação de destino público e nova validação de cada redirecionamento antes de acessar uma página externa.
- `app/services/cloudflare_access.py`: valida assinatura RS256, issuer, audience e expiração do JWT Access, se configurado.
- `app/services/extractor.py`: consulta robots.txt e extrai conteúdo/metadados com Trafilatura; falhas resultam em metadados de descoberta, não em perda do artigo.
- `app/services/deduplicator.py`: canonicalização de URLs e comparação convencional de títulos, sem chamada de IA.
- `app/services/ollama.py`: prompts e chamadas separadas de classificação, resumo e consolidação de cobertura multi-fonte.
- `app/services/pipeline.py`: coordena uma execução, persiste resultados antes da IA e deixa itens não processados como `pending_ai`.
- `app/templates/` e `app/static/`: HTML Jinja com escape automático, estilos e interações leves em JavaScript.
- `tests/`: testes de URL/SSRF, serviços simulados, persistência, tradução e endpoints.

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

O container roda sem privilégios, com filesystem raiz somente leitura, sem capabilities e com `no-new-privileges`; apenas `./data` é gravável. O front define CSP restritiva, allowlist `TrustedHost`, limites de tamanho, cabeçalhos anti-frame/anti-sniff, validação de origem e rate-limit nas escritas. `.env` aceita `ALLOWED_HOSTS` separado por vírgulas; inclua o IP LAN e, ao configurar Cloudflare, o hostname público. Nada foi alterado no Cloudflare. Depois, preencha `CF_ACCESS_TEAM_DOMAIN` e `CF_ACCESS_AUDIENCE` para o app validar o JWT RS256 de Access na origem também. Sem essas variáveis, a identidade fica sob responsabilidade do proxy; não encaminhe portas do roteador. O scraper fixa cada conexão aos IPs públicos resolvidos (mitigando DNS rebinding), limita respostas, bloqueia credenciais/protocolos inválidos e revalida redirecionamentos. Conteúdo usa escape automático do Jinja. O rate-limit é local ao processo único; ao escalar workers, use armazenamento compartilhado. Prompt injection e erro factual de LLM permanecem riscos residuais; compare resumo/tradução com as fontes.
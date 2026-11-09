# Arquitetura e decisões

## Organização

```text
app/
  main.py                 rotas HTTP, renderização SSR e ciclo de vida
  config.py               configurações Pydantic e leitura YAML
  database.py             sessões e migração aditiva
  middleware.py           limite de corpo ASGI
  models.py / schemas.py  persistência e contratos de entrada/saída
  services/
    pipeline.py           orquestração de coleta e fila de IA
    deduplicator.py        URLs canônicas e comparação de títulos
    http.py               HTTP público com DNS protegido contra SSRF
    rss.py / search.py    descoberta RSS e SearXNG
    extractor.py          extração e cache limitado de robots.txt
    ollama.py             classificação, resumo, consolidação e tradução
    cloudflare_access.py  verificação JWT opcional
    source_policy.py      exclusão de domínios
    feed_audit.py         auditoria manual de feeds
  templates/index.html    interface Jinja
  static/                 CSS e JS, sem etapa de build
tests/                    API, serviços, migrações e regressões da fila
scripts/                  benchmark offline e testes JavaScript
config.yaml               temas iniciais
sources.yaml              fontes RSS/Atom
```

## Fluxo de coleta

1. Um lock impede duas coletas/processamentos de fila ao mesmo tempo no processo.
2. Um registro `ProcessingRun` guarda início, contadores, resultado e fim.
3. Temas YAML são sincronizados; temas editados na UI (`origin=ui`) são preservados.
4. Buscas são sequenciais por tema/consulta, com limites configuráveis; seguem os feeds.
5. Cada URL é normalizada, filtrada por domínio e comparada por URL canônica.
6. URLs já conhecidas recebem novos temas e commit imediato. Artigos antigos são ignorados conforme configuração.
7. Títulos recentes do mesmo tipo são comparados com limiar original de 0,88.
   Somente ID e título são lidos em blocos de 128. O resultado é fechado mesmo quando há match antecipado.
8. Coberturas semelhantes são agregadas, preservando links de fontes, e voltam à fila de IA.
9. Novos artigos têm HTML extraído respeitando robots.txt. A extração roda em uma thread aguardada,
   sem criar uma fila de trabalho paralela. Falhas de extração preservam os metadados do feed/busca.
10. Artigos são gravados individualmente e disponibilizados mesmo antes da IA.
11. A fila captura apenas IDs limitados por lote; um artigo completo é carregado/processado e removido
    da sessão antes do próximo. Classificação precede resumo ou consolidação, conforme cobertura.
12. Resultados de IA atualizam relevância, categoria, tipo, temas e resumo. Traduções obsoletas são limpas.

O retry agendado é de até 50 artigos a cada cinco minutos; a coleta usa `AI_ARTICLES_PER_RUN`.
Falhas de rede interrompem o lote, preservando pendências; erros de conteúdo são registrados e permitem
seguir para o próximo item. A prioridade continua sendo dos artigos mais recentes, como no original.

## Recursos e limites

- Listagens e template não carregam o corpo `content` dos artigos. Paginação continua compatível.
- Cache robots: 256 origens, TTL de uma hora; falhas expiram em um minuto; descarte por uso recente.
- Uma chamada de inferência por vez, incluindo traduções; espera por acesso de até dois segundos,
  seguida do timeout HTTP de quatro vezes `REQUEST_TIMEOUT_SECONDS`. Contenção aparece como indisponibilidade temporária.
- `OLLAMA_KEEP_ALIVE` solicita descarregamento do modelo após ociosidade. Não limita RAM durante a inferência.
- Respostas públicas têm limite aplicado durante leitura, inclusive conteúdo descomprimido.
- Escritas POST/PUT/PATCH/DELETE têm corpo limitado mesmo sem Content-Length.
- Índices adicionais cobrem descoberta e fila por estado/data/ID. Alterações de schema são aditivas.
- SQLite ativa chaves estrangeiras e espera de locks por cinco segundos nas conexões da aplicação.
- O encerramento cancela e aguarda a coleta inicial; o scheduler cancela seus jobs. Sessões são fechadas no finally.

Não há remoção automática de artigos, coberturas ou histórico: dados permanecem em disco.
Arquivos muito grandes ainda impactam o banco, buscas textuais e backups. A navegação de dias
materializa os dias disponíveis, e agrupamentos podem acumular fontes; não há truncamento silencioso.

## Por que manter a stack

Os desperdícios identificados vêm da seleção de dados e retenção de lotes, não de evidência de
limitação da linguagem. Reescrever em Go ou Rust exigiria substituir ORM, extração e templates,
sem reduzir a RAM do Ollama externo. Mantemos a stack, sem dependências novas.
Índices usam espaço adicional em disco em troca de evitar varreduras dos caminhos de fila.
O frontend mantém navegação HTML, fontes do sistema, diálogos nativos e recursos locais;
nenhum runtime JavaScript é exigido no servidor.

## CT

Não há módulo, rota ou regra chamada CT no material recebido. É necessário esclarecer a finalidade
antes de implementar regras ou testes específicos. O fluxo acima descreve a coleta real do NewsRadar,
sem presumir que ela seja CT.

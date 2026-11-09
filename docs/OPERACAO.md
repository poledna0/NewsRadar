# Instalação, operação e manutenção

## Ambiente

Use Python 3.12+ e a raiz do repositório como diretório de trabalho. SQLite vem com Python.
Instale dependências em virtualenv conforme README. Ollama deve oferecer `/api/generate`,
com modelo compatível com JSON e o campo `think: false`. SearXNG deve habilitar JSON (ver SEARXNG.md).
Não há etapa de build do frontend. Uvicorn serve Jinja e arquivos estáticos diretamente.
Docker é opcional e não está disponível no ambiente usado nesta refatoração.

Para uso sem coleta automática inicialmente, configure `COLLECT_ON_START=false`.
Isso só desabilita a coleta de startup; o agendamento periódico continua ativo.
Para preparar o modelo na máquina que executa Ollama: `ollama pull qwen3.5:9b` (ou seu modelo).
Tamanho e memória dependem do modelo, quantização, contexto e configuração do Ollama externo.

## Configuração

Copie `.env.example` para `.env`; o arquivo real é ignorado pelo Git e pelo contexto Docker.
Variáveis do ambiente prevalecem sobre `.env`. Caminhos YAML relativos são resolvidos pela raiz
no código; caminho relativo de banco e arquivo `.env` dependem do diretório de execução.

| Variável | Padrão | Finalidade/limites |
|---|---|---|
| APP_NAME | NewsRadar | Configuração de nome; título HTTP/template permanecem NewsRadar |
| APP_PORT | 8000 | Porta publicada no Compose; em execução direta use `--port` do Uvicorn |
| APP_BIND | 127.0.0.1 | Interface publicada pelo Compose |
| APP_UID / APP_GID | 1000 / 1000 | Usuário do container e permissão do volume; args de build também podem ser ajustados |
| DATABASE_URL | sqlite:///./data/newsradar.db | Banco SQLAlchemy; SQLite é o banco contemplado no deploy |
| SEARXNG_URL | http://localhost:8080 | Origem da busca, acessível do processo/container |
| OLLAMA_URL | http://localhost:11434 | Origem da inferência |
| OLLAMA_MODEL | qwen3.5:9b | Modelo previamente instalado no Ollama |
| OLLAMA_KEEP_ALIVE | 60s | Solicitação de retenção do modelo após inferência; `0` solicita descarregamento imediato |
| TRANSLATION_DEFAULT_TARGET | pt-BR | pt-BR ou en |
| COLLECTION_INTERVAL_MINUTES | 30 | Mínimo 5 |
| MAX_RESULTS_PER_QUERY | 10 | 1–50 |
| MAX_RESULTS_PER_FEED | 20 | 1–100 |
| MAX_QUERIES_PER_TOPIC | 4 | 1–10; formulário aceita até oito consultas |
| MAX_RESEARCH_RESULTS_PER_TOPIC | 5 | 1–20 |
| ARTICLE_MAX_AGE_HOURS | 48 | Mínimo 1; verificação durante ingestão, não apaga histórico |
| AI_ARTICLES_PER_RUN | 200 | 1–500; retry agendado usa 50 |
| REQUEST_TIMEOUT_SECONDS | 15 | >0 e <=120; Ollama usa quatro vezes esse valor |
| MAX_HTTP_RESPONSE_BYTES | 8000000 | 100000–25000000 para RSS/HTML público |
| MAX_REQUEST_BODY_BYTES | 64000 | 1024–1000000 para escritas HTTP |
| HTTP_USER_AGENT | NewsRadar/0.1 (+self-hosted news aggregator) | Identificação HTTP/robots |
| ALLOWED_HOSTS | localhost,127.0.0.1,host.docker.internal | Lista separada por vírgulas, sem esquema/porta |
| EXCLUDED_DOMAINS | Lista em .env.example | Domínio e subdomínios excluídos de coleta/listagem; sem remoção de dados |
| CF_ACCESS_TEAM_DOMAIN | vazio | Domínio da equipe, sem https://, configurado junto à audiência |
| CF_ACCESS_AUDIENCE | vazio | Audiência JWT; configure junto ao domínio |
| COLLECT_ON_START | true | Dispara coleta inicial |
| RESPECT_ROBOTS_TXT | true | Respeita robots; falhas de consulta mantêm política original de permitir extração |
| CONFIG_FILE | config.yaml | Temas iniciais YAML |
| SOURCES_FILE | sources.yaml | Feeds YAML |

`languages` no config.yaml é lido pelo objeto Settings, mas não altera as consultas do SearXNG
na implementação atual. Não há seletor de idioma da busca.
Configurações `.env` são carregadas em cache por processo; reinicie para aplicar alterações.
YAML é relido durante sincronização. Desative feeds com `enabled: false`.

## Persistência e atualizações

Banco, artigos, fontes, temas e execuções ficam em `data/newsradar.db`.
O startup cria tabelas/colunas/índices faltantes sem apagar dados. Faça backup antes de atualizar:

```sh
python -c "import sqlite3; s=sqlite3.connect('data/newsradar.db'); d=sqlite3.connect('data/newsradar.backup.db'); s.backup(d); d.close(); s.close()"
```

Use um nome de backup novo por atualização. Preserve também os YAML e `.env` fora do repositório.
Para restaurar, pare o serviço e restaure o arquivo validado com as permissões corretas.
Não copie um arquivo de banco que esteja sendo escrito sem usar o mecanismo de backup do SQLite.
Para rollback de código, selecione o commit anterior; índices/colunas aditivos permanecem compatíveis.

No Compose, verifique propriedade de `data` e ajuste APP_UID/GID. O rootfs é read-only e somente
`data` e `/tmp` são graváveis. Publique atrás de proxy HTTPS e controle de acesso; mantenha o acesso
direto à origem restrito. Execute um worker. Dimensione memória separadamente para app e Ollama.
Não foram definidos limites arbitrários de memória de container sem medição de carga real.

## Troubleshooting

| Sintoma | Verificação |
|---|---|
| pip não encontra pacotes | Teste DNS/acesso ao PyPI; não confunda ausência de rede com inexistência da dependência |
| `Invalid host header` | Adicione o hostname usado em ALLOWED_HOSTS e reinicie |
| Banco não abre | Confira diretório de trabalho, DATABASE_URL e escrita em data |
| `database is locked` | Confirme worker único e ausência de outros escritores prolongados |
| Sem resultados | Remova filtros, veja dia/tipo, temas ativos e conectividade das fontes |
| SearXNG 403 | Habilite formato JSON e confira URL/rede do container |
| IA pendente | Confira OLLAMA_URL, modelo instalado e logs; lote é retomado após cinco minutos |
| Tradução 503 | Backend indisponível, ocupado por outra inferência ou resultado inválido; tente novamente |
| Coleta 403 | Cliente deve ter IP privado/loopback; confira também Origin e proxy |
| Escrita 429 | Aguarde janela da cota; não aumente workers para contornar limite |
| API 413/422 | Reduza corpo ou corrija campos e limites de consulta |
| Fonte sem texto | Robots, erro HTTP ou extração; metadados e link original permanecem |
| Consumo alto de RAM | Meça processo web e Ollama separadamente; reduza lote, limites e retenção do modelo com base no perfil |
| SSH falha na configuração do sistema | Neste ambiente, `ssh -F /dev/null` evita configuração de sistema inválida; não desative verificação de host |
| GitHub não resolve | Sem DNS/rede não é possível fetch/push; a presença de chave não corrige conectividade |

Auditoria de feeds: `python -m app.services.feed_audit`.
Logs: saída padrão do Uvicorn ou `docker compose logs -f newsradar`.
`/health` valida somente HTTP/banco; não comprova que Ollama ou SearXNG estejam operacionais.

## Validação antes de deploy

Execute pytest, compilação, teste de API e navegação em desktop/tablet/mobile com suas dependências
instaladas. Confirme coleta RSS, busca, fila, tradução e autenticação no ambiente real.
Use `pip-audit` no ambiente instalado para auditoria de dependências; a auditoria não foi executada
nesta entrega por indisponibilidade de pacotes/rede. Os intervalos de versões originais foram mantidos,
sem alegação de ausência de vulnerabilidades ou reprodutibilidade de versões não instaladas.

# Relatório técnico — refatoração de 09/11/2026

## Escopo entregue

Código alterado diretamente na pasta `NewsRadar-main`. ZIP original preservado no diretório pai.
Stack mantida: Python, FastAPI, SQLAlchemy/SQLite, Jinja, JavaScript e CSS nativos.
Nenhuma dependência nova foi adicionada. Diagnóstico e justificativa em DIAGNOSTICO.md e ARQUITETURA.md.

Mudanças principais:

- Deduplicação usa cursor incremental com projeção ID/título, sem materializar conteúdos de todos os candidatos.
- Fila captura IDs e processa um documento por vez, remove objeto da sessão e libera o payload após uso.
- Listagens não carregam `content`; índices cobrem descoberta e processamento por estado/data/ID.
- Cache robots limitado a 256 origens com TTL; extração HTML aguarda thread para liberar o event loop.
- Tradução e IA usam uma inferência simultânea; backend inacessível interrompe lote evitando timeouts em cascata.
- Coleta inicial é acompanhada e cancelada no shutdown. Sessões continuam fechadas nos caminhos de erro.
- Duplicatas persistem temas/coberturas imediatamente; títulos são comparados entre publicações do mesmo tipo.
- Autor extraído é preservado; traduções antigas são invalidadas quando resumo/título muda.
- Limite ASGI para corpo real de escrita; validação segura de Content-Length, texto em branco e tamanho de consultas.
- Compose publica em loopback por padrão, com bind configurável; contexto Docker exclui dados e segredos.
- Frontend reorganizado com painel de exploração, cartões, nova tipografia/paleta, layouts responsivos,
  foco visível, link para pular navegação, feedback de erros no formulário e estados de coleta corretos.
- Documentação consolidada e guias de arquitetura, API, operação, diagnóstico e resultados adicionados.

Não foram apagados dados, temas, fontes, funcionalidades ou configurações de produção.

## Benchmark executado

Comando: `python3 scripts/benchmark.py`. Cinco rodadas alternadas de subprocessos independentes,
mesmo banco SQLite sintético com 1.500 registros, 32 KiB de conteúdo + 8 KiB de tradução por registro,
mesmo índice e ordenação. Antes: `SELECT *` + `fetchall`. Depois: ID/título + `fetchmany(128)`.
Métricas são medianas. RSS máximo via `resource.getrusage`, CPU via `process_time`, tempo via
`perf_counter`, alocações Python via `tracemalloc`. Ambiente e amostras em [benchmark.json](benchmark.json).

**É uma comparação isolada dos padrões de leitura do banco, sem ORM, sem comparação de títulos,
sem FastAPI, sem tráfego HTTP e sem IA. Não é profiling end-to-end nem comprovação de RAM do serviço.**
O padrão original foi identificado no código antes das alterações. O experimento foi executado depois,
reproduzindo ambos os padrões em condições equivalentes. Não se apresenta isso como medição de um servidor original em execução.

| Métrica do experimento SQLite | Antes | Depois |
|---|---:|---:|
| Pico de RSS do subprocesso | 81,30 MiB | 21,51 MiB |
| Pico de alocação Python | 59,03 MiB | 0,036 MiB |
| Tempo da leitura | 58,47 ms | 3,13 ms |
| CPU da leitura | 58,47 ms | 3,15 ms |
| Registros verificados | 1.500 | 1.500 |
| CSS + JS, bytes sem compressão | 24.086 | 21.177 |
| CSS + JS, bytes gzip calculados offline | 6.042 | 5.795 |

As últimas duas linhas comparam arquivos reais do commit original com os alterados, não o experimento SQLite.
Gzip é apenas medida de compressibilidade; a aplicação não configura compressão HTTP automaticamente.
A extração de conteúdo e a complexidade da comparação fuzzy não são aceleradas por esse benchmark.
O banco real pode ter tamanhos, cache de SO e distribuição de títulos muito diferentes.

| Métrica do serviço solicitada | Resultado |
|---|---|
| RAM em repouso/sob carga | Não medida; dependências e serviços indisponíveis |
| Uso de CPU sob carga HTTP | Não medido |
| Tempo de inicialização | Não medido |
| Latência das operações/API | Não medida |
| Tempo de criação de CT | Não medido; funcionalidade CT não identificada |
| Build Docker | Não executado; Docker indisponível |

Para perfil real, use checkout original e refatorado em ambientes separados com cópia do mesmo banco,
mesmos serviços/modelo, configuração e carga. Separe PIDs de web, Ollama e SearXNG. Registre aquecimento,
latência mediana/p95, RSS em repouso/pico e CPU. Não substitua essas medições pela tabela sintética.

## Validações executadas

- `python3 -m unittest discover -s tests -p test_core_unittest.py -v`: **6 testes passaram**.
  Cobrem URL com credenciais, remoção de rastreamento, iterador interrompido no primeiro match,
  corpo fragmentado acima do limite, limite exato e desconexão.
- `gjs scripts/check_frontend.js`: **sintaxe e 4 cenários passaram**: sucesso JSON,
  erro de validação estruturado, erro textual e resposta sem JSON.
- `python3 -m compileall -q app tests scripts`: passou (verificação sintática, não execução integrada).
- `git diff --check`: passou.
- Benchmark SQLite offline: executado, amostras registradas.
- Instalação de `requirements-dev.txt`: falhou por indisponibilidade de DNS/PyPI.
- `/tmp/newsradar-venv/bin/python -m pytest -q`: não iniciou; `No module named pytest`.

Novos testes pytest foram escritos para commits de duplicatas, seleção do mesmo tipo, fila de um
artigo por vez, falha de backend, resposta inválida, TTL/limite do cache, traduções antigas e
consultas de listagem sem conteúdo. **Não foram executados.**

## Pendências e limites

1. Executar suíte completa e integração em ambiente com dependências, Ollama e SearXNG.
2. Validar visualmente desktop/tablet/mobile e teclado em navegador real; GJS não faz renderização.
3. Executar build Docker e auditoria de dependências instaladas; versões originais permanecem em intervalos,
   sem garantia de ausência de vulnerabilidades ou lockfile validado.
4. Esclarecer CT: nenhuma rota/módulo/documentação correspondente no ZIP. Não foram inventadas regras.
5. Verificar RSS/busca por fonte: falhas internas ainda podem aparecer apenas em logs e não em todos os
   contadores de ProcessingRun. Campos históricos de monitoramento das fontes não formam um health check completo.
6. Cache de chaves Cloudflare pode ser atualizado frequentemente por tokens com kid desconhecido;
   mantenha restrição de origem/rate limiting no proxy. Autenticação continua opcional.
7. Arquivo de dias e número de fontes de um acontecimento crescem com o histórico; não foi aplicada
   truncagem que eliminaria funcionalidades/dados. Busca textual fuzzy continua proporcional aos candidatos recentes.
8. Não há medição do modelo 9B externo. Descarregar após ociosidade troca memória por latência de recarga.

A entrega não deve ser considerada homologada nem pronta para produção sem concluir essas verificações.

## GitHub

Commits usam `poledna0 <henriquepoledna@proton.me>`; remoto configurado para
`git@github.com:poledna0/NewsRadar.git`, branch local `main`.
O acesso remoto falhou por DNS (`Could not resolve hostname github.com`).
A configuração SSH do sistema também apresentou erro de permissão; o teste com `ssh -F /dev/null`
contornou a configuração, mas não a falta de DNS. Não houve push confirmado.

Como a origem recebida foi um ZIP, o histórico local começa com um snapshot. Quando houver rede,
primeiro faça fetch e confira o histórico da main remota; use um clone da branch remota e reaplique
os commits de alterações, sem o snapshot raiz, se os históricos não forem relacionados.
**Não use force push para substituir a main.** Preserve eventuais mudanças remotas.

## Execução

Instale os requisitos conforme [README](../README.md), configure `.env` e execute:

```sh
uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 --no-server-header
```

Veja [OPERACAO.md](OPERACAO.md) para configuração, backup, deploy e troubleshooting.

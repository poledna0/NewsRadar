# Diagnóstico e plano

A origem é `NewsRadar-main.zip`, preservada no diretório pai. Baseline Git: `527082c`.
Não foram encontrados componentes de CT no código ou na documentação. É necessário esclarecer
se CT pertence a outro projeto ou significa uma operação existente do agregador.

## Evidências no código original

- `_ingest` selecionava todos os campos de todos os artigos dos últimos três dias em cada item,
  incluindo conteúdo e traduções; custo proporcional ao volume de conteúdo vezes os itens recebidos.
- `_process_pending` materializava até 200 artigos completos antes de começar o processamento.
- `article_query` carregava `content`, que não é devolvido pela API nem usado pelo template.
- `_robots_cache` não possuía limite de entradas nem expiração.
- Duplicatas por URL/título alteravam relacionamentos sem commit; uma coleta sem novos artigos
  podia perder essas alterações. O primeiro título semelhante podia ser de outro tipo e impedir
  encontrar uma duplicata correta do mesmo tipo.
- Tradução e processamento periódico podiam executar inferências simultâneas.
- A tarefa inicial não era acompanhada no encerramento. Extração HTML bloqueava o event loop.
- Limite de corpo dependia de Content-Length; corpos transmitidos em partes contornavam o limite.
- A UI podia anunciar sucesso mesmo quando o resultado da coleta era `failed`.

## Ordem de implementação

1. Projeção e leitura incremental na deduplicação; fila por IDs; corpo diferido nas listagens.
2. Persistência de duplicatas, cache limitado, inferência serializada e encerramento controlado.
3. Limite real de corpo, validação de formulário e testes de regressão.
4. Redesenho da hierarquia visual e feedback das ações, mantendo SSR e sem framework novo.
5. Guias operacionais, benchmark reproduzível e registro de limitações.

Python/FastAPI, SQLite, Jinja e JavaScript nativo são mantidos. Não há evidência experimental
que justifique uma migração de linguagem. O Ollama externo e seu modelo 9B podem dominar o
consumo total da instalação, mas não há processo Ollama acessível neste ambiente para medi-lo.
Não se atribui esse consumo ao processo web sem medição. `OLLAMA_KEEP_ALIVE=60s` solicita
liberação após ociosidade; não é um limite de RAM e pode aumentar latência após descarregamento.

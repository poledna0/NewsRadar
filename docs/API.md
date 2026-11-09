# API HTTP

Mesma origem da interface. JSON em UTF-8. Swagger/OpenAPI continuam desabilitados.
Autenticação opcional por Cloudflare Access aplica-se a todas as rotas, exceto `/health`.
Sem ela, a origem deve ficar em rede privada. Não há usuários ou papéis internos.

| Método e rota | Entrada e resultado |
|---|---|
| GET `/health` | `{"status":"ok","database":"ok"}` ou 503 |
| GET `/api/articles` | `items`, `total`, `limit`, `offset`; sem corpo integral do artigo |
| GET `/api/articles/{id}` | Metadados, resumo, traduções, temas e fontes; 404 se ausente/excluído |
| GET `/api/topics` | Temas habilitados com ID/nome/consultas/estado |
| POST `/api/topics` | `{name, queries?}`; 201; reativa tema desativado; 409 se ativo |
| PUT `/api/topics/{id}` | `{name, queries?}`; 200; preserva edição frente ao YAML |
| DELETE `/api/topics/{id}` | Desativa; 204 sem corpo; mantém histórico |
| GET `/api/sources` | Fontes não excluídas e metadados de monitoramento |
| POST `/api/collect` | Aguarda coleta; resultado com `status`, `discovered`, `new`, `duplicates`, `errors`; 409 se ocupada |
| POST `/api/translate` | `{text, target?}`; `{translation,target}`; texto não vazio até 12.000 caracteres |
| POST `/api/articles/{id}/translate` | Query `target=pt-BR` ou `en`; tradução armazenada por idioma |
| GET `/api/stats` | `articles`, `pending_ai`, `sources`, `topics`, `last_collection` |

Listagem aceita `topic`, `hours` (1–720), `day` (ISO YYYY-MM-DD), `source`, `search` (até 200),
`kind=news|research`, `sort=date|relevance`, `limit` (1–100, padrão 50), `offset` (>=0).
A home usa `page` com 30 itens, `day=latest|all|YYYY-MM-DD`, `view=latest|events` e os mesmos filtros pertinentes.

Nome de tema: 2–60 caracteres, sem espaços nas extremidades, letras/números e separadores ` +.#-`.
Até oito consultas, cada uma até 160 caracteres; vazias são removidas e duplicadas normalizadas.
Excesso retorna 422, sem truncar silenciosamente a entrada.

```sh
curl 'http://127.0.0.1:8000/api/articles?kind=research&limit=10'
curl -X POST http://127.0.0.1:8000/api/topics \
  -H 'Content-Type: application/json' \
  -d '{"name":"Linux","queries":["linux kernel"]}'
curl -X POST http://127.0.0.1:8000/api/translate \
  -H 'Content-Type: application/json' \
  -d '{"text":"Hello world","target":"pt-BR"}'
```

Erros usam `detail` (texto ou lista de validações Pydantic). Códigos: 401 identidade ausente/inválida,
403 origem/rede recusada, 404 ausente, 409 conflito/ocupado, 413 corpo acima do limite,
422 entrada inválida, 429 cota local, 503 serviço indisponível.
Uma coleta pode retornar HTTP 200 e `status=failed`; examine sempre o estado e contadores.
Fontes individuais podem falhar e produzir apenas logs sem incrementar todos os contadores de erro.

Cotas por cliente e ação: temas 10/hora, tradução 10/minuto, coleta 2/10 minutos.
Aplicadas no processo, adequadas a um único worker; não são proteção distribuída.
Requisições de escrita validam Origin/Referer/Sec-Fetch-Site quando presentes.
Coleta manual exige IP privado/loopback. Ao usar proxy, configure de forma restrita os IPs confiáveis
no Uvicorn; não confie em cabeçalhos encaminhados por clientes arbitrários.

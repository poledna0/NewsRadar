# Contribuindo

Obrigado por considerar uma contribuição ao NewsRadar. O projeto prioriza simplicidade operacional, privacidade e execução local.

## Antes de começar

1. Procure issues existentes para evitar trabalho duplicado.
2. Para mudanças grandes, abra uma issue descrevendo o problema e a solução proposta.
3. Não inclua tokens, URLs privadas, dados pessoais ou bancos de produção em commits.

## Ambiente de desenvolvimento

Requisitos: Python 3.12+ e, opcionalmente, Docker Compose.

```sh
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
pytest -q
```

Os testes devem ser determinísticos: simule HTTP, SearXNG e Ollama em vez de depender de serviços externos.

## Diretrizes

- Mantenha FastAPI, Jinja e JavaScript leve; não introduza um frontend pesado sem uma necessidade clara.
- Valide dados externos e mantenha SearXNG/Ollama como infraestrutura configurável.
- Preserve dados existentes: alterações de schema precisam de migração aditiva e teste.
- Trate resultados de RSS, scraping e LLM como entrada não confiável.
- Prefira comentários curtos para explicar decisões de segurança ou fluxo não óbvias.
- Atualize README ou `docs/` quando mudar instalação, configuração ou comportamento da API.

## Pull requests

- Uma mudança focada por PR, com contexto e comportamento esperado.
- Inclua testes para novos caminhos ou correções.
- Rode `pytest -q` e descreva o resultado.
- Use commits Conventional Commits com descrição concisa em português, por exemplo `feat: adiciona filtro por fonte` ou `fix: valida destino de redirecionamento`.
- Não inclua alterações geradas, `.env`, banco SQLite ou credenciais.

## Revisão

PRs são avaliados por segurança, compatibilidade com self-hosting, legibilidade, testes e manutenção de dados. Uma contribuição pode ser solicitada em partes menores antes de ser aceita.

# NewsRadar

Agregador local de notícias e pesquisa com RSS/Atom, descoberta por SearXNG,
deduplicação, resumos por Ollama e tradução para português ou inglês.
Interface responsiva em português, renderizada no servidor, sem framework JavaScript ou build Node.

Python/FastAPI, SQLAlchemy/SQLite, Jinja, JavaScript nativo e CSS. Ollama e SearXNG são serviços externos.
Resumos e classificações de IA podem conter erros: confira as fontes originais.

## Instalação local

Requisitos: Python 3.12 ou superior e acesso ao PyPI para instalar as dependências.
SearXNG é necessário para buscas; Ollama com o modelo configurado para IA e traduções.
Sem esses serviços, o acervo continua consultável; RSS não depende de SearXNG.

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
mkdir -p data
uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 --no-server-header
```

Execute a partir da raiz do projeto. Acesse http://127.0.0.1:8000 e `/health`.
O exemplo `.env` usa serviços em localhost. Ajuste URLs para sua instalação.
Para desenvolver: instale `requirements-dev.txt` e acrescente `--reload` ao comando acima.
Não combine reload com produção. Use um único worker para não duplicar agendamentos e modelos em memória.

## Produção com Docker

```sh
cp .env.example .env
mkdir -p data
```

Configure `.env`: `APP_UID`/`APP_GID` devem corresponder ao proprietário de `data`;
SearXNG e Ollama precisam de URLs acessíveis de dentro do container, por exemplo
`http://host.docker.internal:8080` e `http://host.docker.internal:11434`.
A configuração depende de onde seus serviços estão instalados; o Compose não os cria.

```sh
docker compose up -d --build
docker compose logs -f newsradar
curl http://127.0.0.1:8000/health
```

O bind padrão é `127.0.0.1`. Para acesso pela LAN, configure `APP_BIND` com a interface apropriada
junto a firewall, `ALLOWED_HOSTS` e controle de acesso. Não exponha a origem pública sem autenticação.
Veja [operação e deploy](docs/OPERACAO.md) e [segurança](SECURITY.md).

## Uso

- **+ Tema**: nome e até 8 consultas de até 160 caracteres cada. Consultas vazias usam o nome.
- Temas podem ser editados ou desativados sem apagar o histórico. Alterações na UI prevalecem sobre YAML.
- **Coletar**: busca notícias/papers por tema, lê feeds de `sources.yaml`, agrupa duplicatas e processa IA.
- Filtros por tema, tipo, dia, fonte, período e texto; ordenação por data ou relevância.
- Arquivo diário e paginação de 30 itens. “Múltiplas fontes” mostra coberturas agrupadas.
- **Traduzir**: texto livre ou resumo de artigo. Selecione pt-BR ou inglês no topo.
- Traduções de artigos são armazenadas por idioma e invalidadas quando o resumo ou título é atualizado.

A coleta automática ocorre a cada 30 minutos, e a fila de IA é retomada a cada 5 minutos.
Se Ollama ficar indisponível, o lote de IA para no primeiro erro de conexão para evitar timeouts repetidos;
as publicações continuam pendentes para o próximo ciclo. Resultados malformados não interrompem os demais artigos.

## Testes e medições

```sh
pip install -r requirements-dev.txt
python -m pytest -q
python -m compileall -q app tests scripts
python scripts/benchmark.py
```

Sem dependências: `python -m unittest discover -s tests -p test_core_unittest.py -v`.
Opcional, com GJS instalado: `gjs scripts/check_frontend.js`.

**Estado da validação desta entrega:** seis testes offline e quatro cenários JavaScript passaram;
compilação Python e checagem de diff passaram. A suíte pytest, execução integrada e revisão visual em navegador
ficaram bloqueadas por dependências indisponíveis e DNS restrito. Não considerar o deploy validado em produção.
O benchmark é sintético do acesso SQLite, não do serviço completo. Resultados e limitações no relatório.

## Documentação

- [Relatório, benchmarks e pendências](docs/RELATORIO.md)
- [Diagnóstico inicial e plano](docs/DIAGNOSTICO.md)
- [Arquitetura, decisões e fluxo de coleta/IA](docs/ARQUITETURA.md)
- [Configuração, instalação, deploy e troubleshooting](docs/OPERACAO.md)
- [APIs e exemplos](docs/API.md)
- [Configuração SearXNG](docs/SEARXNG.md)
- [Contribuição](CONTRIBUTING.md) e [segurança](SECURITY.md)

A sigla **CT** não consta no projeto recebido. A revisão específica de CT depende de sua definição
ou do fornecimento do código correspondente; nenhum fluxo de negócio foi inventado para substituí-la.

Licença Apache 2.0: [LICENSE](LICENSE).

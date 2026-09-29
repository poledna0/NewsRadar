# SearXNG para o NewsRadar

O NewsRadar usa a API JSON do SearXNG. A busca HTML pode funcionar enquanto JSON retorna `403`; nesse caso, habilite `json` na configuração da instância.

## Configuração existente

No `settings.yml` montado em `/etc/searxng/settings.yml`, preserve suas opções atuais e acrescente:

```yaml
search:
  formats:
    - html
    - json
```

Faça backup antes de editar e reinicie somente o serviço SearXNG. Valide no host:

```sh
curl -i 'http://127.0.0.1:PORTA/search?q=linux&format=json'
```

A resposta esperada é HTTP 200 e JSON com `results`. A categoria de pesquisa também deve funcionar:

```sh
curl -i 'http://127.0.0.1:PORTA/search?q=linux+research&format=json&categories=science'
```

## Exemplo Compose opcional

Este exemplo é para instalação nova. Não o use sobre uma instalação existente sem revisar redes, armazenamento, secret e política de atualização. SearXNG continua separado do Compose do NewsRadar.

```yaml
services:
  searxng:
    image: searxng/searxng:latest
    restart: unless-stopped
    ports:
      - "127.0.0.1:6767:8080"
    volumes:
      - ./searxng:/etc/searxng:rw
    environment:
      SEARXNG_BASE_URL: http://localhost:6767/
```

Crie `./searxng/settings.yml` com um `server.secret_key` aleatório gerado no host e as opções `search.formats` acima. Não reutilize o segredo deste exemplo em documentação ou commits. Para persistência/cache em produção, configure Valkey conforme a documentação oficial do SearXNG.

Se o NewsRadar estiver em outro container, configure `SEARXNG_URL` com um endereço alcançável pelo container. Para a publicação de host `6767:8080`, normalmente é `http://host.docker.internal:6767`; confira firewall e `extra_hosts` da instalação. Não exponha uma API SearXNG aberta à internet sem controles de rede.

No `.env` do NewsRadar:

```dotenv
SEARXNG_URL=http://host.docker.internal:6767
```

A configuração da instalação real do servidor está fora deste repositório e não deve ser substituída automaticamente por este exemplo.

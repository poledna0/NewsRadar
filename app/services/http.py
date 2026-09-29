import asyncio
import ipaddress
import socket
from urllib.parse import urljoin, urlsplit

import httpx

from app.config import get_settings


def _host_is_public(host: str) -> bool:
    if host.lower() in {"localhost", "localhost.localdomain"} or host.endswith((".localhost", ".local")):
        return False
    try:
        addresses = [ipaddress.ip_address(host)]
    except ValueError:
        try:
            addresses = [
                ipaddress.ip_address(result[4][0])
                for result in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
            ]
        except (OSError, ValueError):
            return False
    return bool(addresses) and all(address.is_global for address in addresses)


async def validate_public_url(url: str) -> bool:
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
        return False
    return await asyncio.to_thread(_host_is_public, parts.hostname)


async def get_public_response(client: httpx.AsyncClient, url: str, attempts: int = 2) -> httpx.Response:
    current_url = url
    for redirect in range(4):
        if not await validate_public_url(current_url):
            raise ValueError("URL de destino não pública ou inválida")
        response = None
        for attempt in range(attempts):
            try:
                response = await client.get(current_url, follow_redirects=False)
                if response.status_code not in {429, 500, 502, 503, 504} or attempt + 1 == attempts:
                    break
            except httpx.HTTPError:
                if attempt + 1 == attempts:
                    raise
            await asyncio.sleep(0.4 * (attempt + 1))
        if response is None:
            raise httpx.RequestError("A requisição não retornou resposta")
        if response.is_redirect:
            if redirect == 3 or not response.headers.get("location"):
                raise httpx.TooManyRedirects("Limite de redirecionamentos excedido", request=response.request)
            current_url = urljoin(current_url, response.headers["location"])
            continue
        response.raise_for_status()
        return response
    raise httpx.TooManyRedirects("Limite de redirecionamentos excedido")


def make_client() -> httpx.AsyncClient:
    settings = get_settings()
    return httpx.AsyncClient(
        timeout=httpx.Timeout(settings.request_timeout_seconds),
        headers={"User-Agent": settings.http_user_agent},
        trust_env=False,
    )
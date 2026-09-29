import asyncio
import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import aiohttp
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


class PublicResolver(aiohttp.abc.AbstractResolver):
    """Resolve and pin every scraping connection to globally routable addresses."""

    async def resolve(self, host: str, port: int = 0, family: int = socket.AF_UNSPEC) -> list[dict]:
        loop = asyncio.get_running_loop()
        records = await loop.getaddrinfo(host, port, family=family, type=socket.SOCK_STREAM)
        addresses = {}
        for resolved_family, _, protocol, _, sockaddr in records:
            address = ipaddress.ip_address(sockaddr[0].split("%", 1)[0])
            if not address.is_global:
                raise OSError("Resolved destination is not globally routable")
            addresses[(resolved_family, str(address))] = {
                "hostname": host,
                "host": str(address),
                "port": port,
                "family": resolved_family,
                "proto": protocol or socket.IPPROTO_TCP,
                "flags": 0,
            }
        if not addresses:
            raise OSError("Host did not resolve to a public address")
        return list(addresses.values())

    async def close(self) -> None:
        return None


@dataclass
class PublicResponse:
    status_code: int
    headers: dict
    content: bytes

    @property
    def text(self) -> str:
        content_type = self.headers.get("Content-Type", "")
        charset = content_type.partition("charset=")[2].split(";", 1)[0].strip(" \"'")
        try:
            return self.content.decode(charset or "utf-8", errors="replace")
        except LookupError:
            return self.content.decode("utf-8", errors="replace")


def _valid_public_url_shape(url: str) -> bool:
    parts = urlsplit(url)
    return parts.scheme in {"http", "https"} and bool(parts.hostname) and not parts.username and not parts.password


async def get_public_response(url: str, attempts: int = 2) -> PublicResponse:
    if not _valid_public_url_shape(url):
        raise ValueError("URL de destino inválida")
    settings = get_settings()
    timeout = aiohttp.ClientTimeout(total=settings.request_timeout_seconds)
    connector = aiohttp.TCPConnector(resolver=PublicResolver(), use_dns_cache=False)
    async with aiohttp.ClientSession(timeout=timeout, connector=connector, headers={"User-Agent": settings.http_user_agent}, trust_env=False) as client:
        current_url = url
        for redirect in range(4):
            if not _valid_public_url_shape(current_url):
                raise ValueError("Redirecionamento para URL inválida")
            response = None
            for attempt in range(attempts):
                try:
                    async with client.get(current_url, allow_redirects=False) as upstream:
                        if upstream.content_length and upstream.content_length > settings.max_http_response_bytes:
                            raise RuntimeError("External response exceeds the configured size limit")
                        body = bytearray()
                        async for chunk in upstream.content.iter_chunked(64 * 1024):
                            if len(body) + len(chunk) > settings.max_http_response_bytes:
                                raise RuntimeError("External response exceeds the configured size limit")
                            body.extend(chunk)
                        response = PublicResponse(upstream.status, dict(upstream.headers), bytes(body))
                    if response.status_code not in {429, 500, 502, 503, 504} or attempt + 1 == attempts:
                        break
                except (aiohttp.ClientError, asyncio.TimeoutError, OSError):
                    if attempt + 1 == attempts:
                        raise
                await asyncio.sleep(0.4 * (attempt + 1))
            if response is None:
                raise RuntimeError("A requisição externa não retornou resposta")
            if response.status_code in {301, 302, 303, 307, 308}:
                if redirect == 3 or not response.headers.get("Location"):
                    raise ValueError("Limite de redirecionamentos excedido")
                current_url = urljoin(current_url, response.headers["Location"])
                continue
            if response.status_code >= 400:
                raise RuntimeError(f"O servidor externo respondeu HTTP {response.status_code}")
            return response
    raise ValueError("Limite de redirecionamentos excedido")


def make_client() -> httpx.AsyncClient:
    settings = get_settings()
    return httpx.AsyncClient(
        timeout=httpx.Timeout(settings.request_timeout_seconds),
        headers={"User-Agent": settings.http_user_agent},
        trust_env=False,
    )
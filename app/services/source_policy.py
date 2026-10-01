def is_excluded_domain(hostname: str | None, excluded_domains: list[str]) -> bool:
    """Match a blocked registrable domain and all its subdomains."""
    host = (hostname or "").strip().lower().rstrip(".")
    return any(host == domain or host.endswith(f".{domain}") for domain in excluded_domains)
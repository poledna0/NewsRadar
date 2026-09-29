import json
import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


async def _generate(prompt: str) -> str:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=httpx.Timeout(settings.request_timeout_seconds * 4), trust_env=False) as client:
        response = await client.post(
            f"{settings.ollama_url.rstrip('/')}/api/generate",
            json={
                "model": settings.ollama_model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.1},
            },
        )
        response.raise_for_status()
        return response.json()["response"]


async def classify(article: dict, topic_names: list[str]) -> dict:
    prompt = f"""Você é um editor técnico e neutro. Classifique apenas com base nos dados fornecidos.
Retorne JSON com relevance_score (inteiro 0-100), category (texto curto), topics (itens somente da lista) e important (booleano).
Não invente informações. Categorias e tópicos devem refletir o conteúdo, não apenas palavras isoladas.

Tópicos disponíveis: {json.dumps(topic_names, ensure_ascii=False)}
Título: {article.get('title', '')}
Fonte: {article.get('source_name', '')}
Descrição: {article.get('description', '')[:3000]}
Conteúdo: {article.get('content', '')[:10000]}
"""
    result = json.loads(await _generate(prompt))
    result["relevance_score"] = max(0, min(100, int(result.get("relevance_score", 0))))
    result["topics"] = [name for name in result.get("topics", []) if name in topic_names]
    return result


async def summarize(article: dict) -> str:
    prompt = f"""Resuma em português, em 3 a 6 frases objetivas. Use somente os fatos no material abaixo.
Não invente nem complete lacunas; preserve nomes, números e datas; atribua claramente alegações às fontes;
seja neutro e não transforme opinião em fato. Retorne JSON com a chave 'summary' contendo o texto.

Título: {article.get('title', '')}
Fonte: {article.get('source_name', '')}
Descrição: {article.get('description', '')[:3000]}
Conteúdo: {article.get('content', '')[:12000]}
"""
    result = json.loads(await _generate(prompt))
    summary = result.get("summary", "").strip()
    if not summary:
        raise ValueError("Ollama retornou resumo vazio")
    return summary


async def consolidate_event(article: dict) -> tuple[str, str]:
    sources = article.get("related_sources", [])
    source_material = [
        {"title": source.get("title"), "source": source.get("name"), "description": source.get("description", "")[:2000]}
        for source in sources
    ]
    prompt = f"""Você é um editor de notícias neutro. Consolide a cobertura de um único acontecimento usando somente as fontes abaixo.
Retorne JSON com 'title' (manchete curta e factual) e 'summary' (3 a 6 frases em português).
Não combine fatos incompatíveis, não invente detalhes e atribua alegações às fontes. Se um detalhe aparece em apenas uma fonte,
atribua-o claramente a ela. Preserve nomes, números e datas.

Cobertura disponível: {json.dumps(source_material, ensure_ascii=False)}
Manchete já armazenada: {article.get('title', '')}
Descrição/conteúdo da fonte principal: {article.get('description', '')[:4000]}\n{article.get('content', '')[:8000]}
"""
    result = json.loads(await _generate(prompt))
    title = result.get("title", "").strip()
    summary = result.get("summary", "").strip()
    if not title or not summary:
        raise ValueError("Ollama retornou consolidação incompleta")
    return title, summary


async def process_article(article: dict, topic_names: list[str]) -> tuple[dict, str, str | None]:
    classification = await classify(article, topic_names)
    if article.get("related_sources"):
        title, summary = await consolidate_event(article)
    else:
        title, summary = None, await summarize(article)
    return classification, summary, title
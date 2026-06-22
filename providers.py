"""
Получение данных от провайдеров: Jackett и Prowlarr.
Ничего не знает про jacred, только про внешние API.
"""
import httpx
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Переиспользуемый HTTP-клиент
_http_client: Optional[httpx.AsyncClient] = None


def get_http_client() -> httpx.AsyncClient:
    """Возвращает глобальный HTTP-клиент (создаёт при первом вызове)."""
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            limits=httpx.Limits(
                max_keepalive_connections=20,
                max_connections=100,
                keepalive_expiry=30.0,
            ),
        )
    return _http_client


async def close_http_client():
    """Закрывает HTTP-клиент при завершении приложения."""
    global _http_client
    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None


# ==================== JACKETT ====================

async def fetch_jackett(config: Dict, params: Dict) -> List[Dict]:
    """Запрос к Jackett API."""
    url = f"{config['url']}/api/v2.0/indexers/all/results"
    client = get_http_client()

    response = await client.get(url, params=params)

    if response.status_code >= 400:
        logger.error(f"Jackett error {response.status_code}: {response.text[:200]}")
        response.raise_for_status()

    data = response.json()
    return data.get("Results", [])


# ==================== PROWLARR ====================

async def fetch_prowlarr(config: Dict, params: Dict) -> List[Dict]:
    """Запрос к Prowlarr API /api/v1/search."""
    url = f"{config['url']}/api/v1/search"
    headers = {"X-Api-Key": config["apikey"]}

    prowlarr_params = {
        "query": params.get("query", params.get("Query", "")),
        "type": "search",
    }

    if "categories" in params:
        prowlarr_params["categories"] = params["categories"]

    client = get_http_client()
    response = await client.get(url, params=prowlarr_params, headers=headers)

    if response.status_code >= 400:
        logger.error(f"Prowlarr error {response.status_code}: {response.text[:200]}")
        response.raise_for_status()

    return response.json()


def prowlarr_to_jackett(item: Dict) -> Dict:
    """
    Адаптер: Prowlarr item → Jackett-совместимый словарь.
    Только маппинг полей, без парсинга.
    """
    attrs = item.get("attributes", [])
    attr_dict = {}
    for a in attrs:
        if isinstance(a, dict):
            attr_dict[a.get("key", "")] = a.get("value", "")

    categories = item.get("categories", [])
    category_ids = [c.get("id", 0) for c in categories] if categories else []
    category_names = [c.get("name", "") for c in categories] if categories else []

    return {
        "Title": item.get("title", ""),
        "Size": item.get("size", 0),
        "Seeders": item.get("seeders", 0) or attr_dict.get("seeders", 0),
        "Peers": item.get("peers", 0) or attr_dict.get("peers", 0),
        "PublishDate": item.get("publishDate", ""),
        "MagnetUri": item.get("magnetUrl") or item.get("downloadUrl") or "",
        "Details": item.get("infoUrl") or item.get("guid", ""),
        "TrackerId": item.get("indexer", "") or item.get("indexerId", ""),
        "Tracker": item.get("indexer", "") or item.get("indexerId", ""),
        "Category": category_ids,
        "CategoryDesc": category_names[0] if category_names else "",
        "Guid": item.get("guid", ""),
        "Link": item.get("downloadUrl") or item.get("magnetUrl", ""),
    }
"""
JACKETT + PROWLARR PROXY
Один pipeline обработки для всех провайдеров
"""
import os
import re
import time
import asyncio
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi import HTTPException

from core import (
    JACKETTS,
    PROWLARRS,
    PROXY_API_KEY,
    jackett_to_jackred,
    should_filter_item,
)
from providers import fetch_jackett, fetch_prowlarr, prowlarr_to_jackett

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))
logger = logging.getLogger(__name__)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

# ==================== КОНСТАНТЫ ====================

CORS_HEADERS = {"Access-Control-Allow-Origin": "*"}
BTIH_RE = re.compile(r"btih:([a-f0-9]{40}|[a-z2-7]{32})", re.IGNORECASE)
COMBINED_NAME = os.getenv("COMBINED_NAME", "all")
PROVIDER_TIMEOUT = int(os.getenv("PROVIDER_TIMEOUT", "15"))

# Приоритет провайдеров при дедупликации
PROVIDER_PRIORITY_RAW = os.getenv("PROVIDER_PRIORITY", "")
PROVIDER_PRIORITY = {}
if PROVIDER_PRIORITY_RAW:
    for i, name in enumerate(p.strip() for p in PROVIDER_PRIORITY_RAW.split(",") if p.strip()):
        PROVIDER_PRIORITY[name] = i

# ==================== КЕШ ДЛЯ RSS ====================

_RSS_CACHE = {}
_RSS_CACHE_TTL = int(os.getenv("RSS_CACHE_TTL", "300"))

# ==================== CIRCUIT BREAKER ====================

CB_MAX_FAILS = int(os.getenv("CB_MAX_FAILS", "3"))
CB_TIMEOUT = int(os.getenv("CB_TIMEOUT", "300"))

_circuit_breakers = {}

def is_circuit_open(name: str) -> bool:
    cb = _circuit_breakers.get(name)
    if cb and cb["open_until"] > time.monotonic():
        return True
    return False

def circuit_success(name: str):
    _circuit_breakers[name] = {"fails": 0, "open_until": 0}

def circuit_fail(name: str):
    cb = _circuit_breakers.setdefault(name, {"fails": 0, "open_until": 0})
    cb["fails"] += 1
    if cb["fails"] >= CB_MAX_FAILS:
        cb["open_until"] = time.monotonic() + CB_TIMEOUT
        logger.warning(f"[{name}] circuit breaker OPEN for {CB_TIMEOUT}s")

# ==================== ИСКЛЮЧЕНИЯ ====================

class ProviderNotFound(LookupError):
    """Провайдер не найден в конфигурации"""
    pass

# ==================== FASTAPI ====================

app = FastAPI(
    title="Proxy",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

# ==================== PIPELINE ====================

def process_items(raw_items: list, source_name: str = "") -> tuple[list, int]:
    """Единый pipeline: конвертация в jacred + фильтрация."""
    converted = []
    filtered_count = 0

    for item in raw_items:
        try:
            result = jackett_to_jackred(item)
            result["_source"] = source_name

            if should_filter_item(
                item,
                result["info"]["voices"],
                result["languages"],
                result["info"]["quality"],
            ):
                filtered_count += 1
                continue

            converted.append(result)

        except Exception:
            logger.exception(f"Item error | title: {item.get('Title', '?')[:80]}")

    return converted, filtered_count


def deduplicate(results: list) -> list:
    """
    Дедупликация по приоритету:
    1. BTIH hash (magnet-ссылка)
    2. Details (ссылка на страницу раздачи)
    3. Title + Size (запасной вариант)

    При дубликате выбирается по PROVIDER_PRIORITY или по сидерам.
    Алгоритм не является транзитивным.
    """
    unique = {}

    for r in results:
        hash_found = None
        for field in ["MagnetUri", "Link", "Guid"]:
            value = r.get(field, "")
            if value:
                m = BTIH_RE.search(str(value))
                if m:
                    hash_found = m.group(1).lower()
                    break

        if hash_found:
            key = ("hash", hash_found)
        else:
            details = r.get("Details", "")
            if details:
                key = ("details", details)
            else:
                key = ("title_size", f"{r.get('Title', '')}_{r.get('Size', 0)}")

        existing = unique.get(key)

        if not existing:
            unique[key] = r
        elif PROVIDER_PRIORITY:
            existing_source = existing.get("_source", "")
            new_source = r.get("_source", "")
            existing_prio = PROVIDER_PRIORITY.get(existing_source, 999)
            new_prio = PROVIDER_PRIORITY.get(new_source, 999)
            if new_prio < existing_prio:
                unique[key] = r
            elif new_prio == existing_prio and r["Seeders"] > existing["Seeders"]:
                unique[key] = r
        else:
            if r["Seeders"] > existing["Seeders"]:
                unique[key] = r

    all_results = list(unique.values())
    all_results.sort(key=lambda x: x.get("Seeders", 0), reverse=True)
    return all_results


# ==================== PROVIDERS ====================

async def get_provider_results(name: str, params: dict) -> list:
    """Возвращает Jackett-совместимые результаты от провайдера."""
    if name in JACKETTS:
        config = JACKETTS[name]
        p = params.copy()
        p["apikey"] = config["apikey"]
        return await fetch_jackett(config, p)

    if name in PROWLARRS:
        config = PROWLARRS[name]
        raw = await fetch_prowlarr(config, params)
        return [prowlarr_to_jackett(item) for item in raw]

    raise ProviderNotFound(f"Provider '{name}' not found")


async def get_and_process_provider(name: str, params: dict) -> list:
    """Получить + обработать одного провайдера."""
    raw = await get_provider_results(name, params)
    converted, filtered = process_items(raw, source_name=name)
    if params.get("Query") or params.get("query"):
        logger.info(f"[{name}] {len(raw)} → {len(converted)} (filtered {filtered})")
    return converted


# ==================== ЭНДПОИНТЫ ====================

@app.get("/health")
async def health():
    """Healthcheck для Docker — без ключа, не опрашивает провайдеров."""
    return JSONResponse(content={"status": "ok"})


@app.get("/api/v2.0/indexers/all/results")
async def root_torznab(request: Request):
    """Запросы без имени провайдера → объединённый результат."""
    return await _combined_results(request)


@app.get("/{name}")
async def short_endpoint(name: str, request: Request):
    """Короткий эндпоинт: /all, /jac, /tst, /prowlarr"""
    return await _handle_provider(name, request)


@app.get("/{name}/api/v2.0/indexers/all/results")
async def full_endpoint(name: str, request: Request):
    """Полный эндпоинт: /all/api/v2.0/indexers/all/results"""
    return await _handle_provider(name, request)


async def _handle_provider(name: str, request: Request):
    """Общий обработчик для коротких и полных эндпоинтов."""

    if name == COMBINED_NAME:
        return await _combined_results(request)

    params = dict(request.query_params)
    params.pop("apikey", None)

    if is_circuit_open(name):
        return JSONResponse(
            content={"Results": [], "error": f"Provider '{name}' temporarily unavailable"},
            status_code=503,
            headers=CORS_HEADERS,
        )

    try:
        converted = await get_and_process_provider(name, params)
        circuit_success(name)

        return JSONResponse(
            content={"Results": converted},
            headers=CORS_HEADERS,
        )

    except ProviderNotFound:
        return JSONResponse(
            content={"Results": [], "error": f"'{name}' not found"},
            status_code=404,
            headers=CORS_HEADERS,
        )

    except Exception:
        logger.exception(f"[{name}] error")
        circuit_fail(name)
        return JSONResponse(
            content={"Results": [], "error": "Internal server error"},
            status_code=500,
            headers=CORS_HEADERS,
        )


async def _combined_results(request: Request):
    """Объединённый результат со всех провайдеров."""
    params = dict(request.query_params)
    params.pop("apikey", None)

    # Кеш для RSS (пустых запросов)
    has_query = bool(params.get("Query") or params.get("query"))
    if not has_query:
        cached = _RSS_CACHE.get("rss")
        if cached and time.monotonic() - cached["time"] < _RSS_CACHE_TTL:
            logger.debug("RSS cache hit")
            return JSONResponse(content={"Results": cached["data"]}, headers=CORS_HEADERS)

    provider_names = list(JACKETTS.keys()) + list(PROWLARRS.keys())

    tasks = []
    task_names = []
    for name in provider_names:
        if is_circuit_open(name):
            logger.debug(f"[{name}] circuit breaker open, skipping")
            continue
        task_names.append(name)
        tasks.append(
            asyncio.wait_for(get_and_process_provider(name, params), timeout=PROVIDER_TIMEOUT)
        )

    all_processed = await asyncio.gather(*tasks, return_exceptions=True)

    combined = []
    for name, result in zip(task_names, all_processed):
        if isinstance(result, asyncio.TimeoutError):
            logger.warning(f"[{name}] timeout ({PROVIDER_TIMEOUT}s)")
            circuit_fail(name)
            continue
        if isinstance(result, Exception):
            logger.error(f"[{name}] error: {result}")
            circuit_fail(name)
            continue
        circuit_success(name)
        combined.extend(result)

    unique = deduplicate(combined)

    if not has_query:
        _RSS_CACHE["rss"] = {"data": unique, "time": time.monotonic()}

    if has_query:
        logger.info(
            f"{COMBINED_NAME}: {len(provider_names)} провайдеров → {len(unique)} уникальных"
        )

    return JSONResponse(content={"Results": unique}, headers=CORS_HEADERS)


# ==================== SHUTDOWN ====================

@app.on_event("shutdown")
async def shutdown():
    from providers import close_http_client
    await close_http_client()
    logger.info("HTTP client closed")


# ==================== ERROR HANDLERS ====================

@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=404,
        content={"error": "Not found"},
        headers=CORS_HEADERS,
    )


@app.exception_handler(405)
async def method_not_allowed_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=405,
        content={"error": "Method not allowed"},
        headers=CORS_HEADERS,
    )


# ==================== SECURITY ====================

try:
    from security_middleware import add_security
    app = add_security(app)
    logger.info("✅ Security middleware loaded")
except ImportError as e:
    logger.exception("Cannot import security middleware")
    raise RuntimeError("Security middleware import failed") from e
except Exception:
    logger.exception("Error loading security middleware")
    raise


# ==================== ЗАПУСК ====================

if __name__ == "__main__":
    import uvicorn

    logger.info("=" * 60)
    logger.info("🚀 Starting Multi-Provider Proxy")
    logger.info("🔒 Security: MAXIMUM")
    logger.info(f"📊 Rate limiting: {'ON' if os.getenv('RATE_LIMIT_ENABLED', 'true') == 'true' else 'OFF'}")
    logger.info(f"📡 Provider timeout: {PROVIDER_TIMEOUT}s")
    logger.info(f"🔁 Circuit breaker: {CB_MAX_FAILS} fails → {CB_TIMEOUT}s open")
    logger.info(f"💾 RSS cache: {_RSS_CACHE_TTL}s")
    if PROVIDER_PRIORITY:
        logger.info(f"⭐ Provider priority: {list(PROVIDER_PRIORITY.keys())}")
    logger.info("")
    logger.info("✅ Providers:")
    for name in JACKETTS:
        logger.info(f"   • /{name} (Jackett)")
    for name in PROWLARRS:
        logger.info(f"   • /{name} (Prowlarr)")
    logger.info(f"   • /{COMBINED_NAME} (объединённый)")
    logger.info(f"   • /api/v2.0/indexers/all/results (Torznab)")
    logger.info("")
    logger.info(f"✅ Также доступны полные пути:")
    for name in JACKETTS:
        logger.info(f"   • /{name}/api/v2.0/indexers/all/results")
    for name in PROWLARRS:
        logger.info(f"   • /{name}/api/v2.0/indexers/all/results")
    logger.info(f"   • /{COMBINED_NAME}/api/v2.0/indexers/all/results")
    logger.info("")
    logger.info("🩺 Healthcheck: /health (no auth)")
    logger.info("❌ Everything else → 404 Not Found")
    logger.info("=" * 60)

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        log_level=LOG_LEVEL.lower(),
        server_header=False,
    )

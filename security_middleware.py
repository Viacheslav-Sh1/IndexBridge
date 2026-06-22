import os
import hmac
import time
import asyncio
import logging
from collections import defaultdict
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("security")

# 🔐 Конфигурация
PROXY_API_KEY = os.getenv("PROXY_API_KEY")
if not PROXY_API_KEY:
    raise RuntimeError("PROXY_API_KEY environment variable is required")

RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "60"))
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))

# ==================== RATE LIMITER ====================

class RateLimiter:
    """
    Потокобезопасный rate limiter с отдельным lock на каждый IP.
    Атомарная проверка + добавление. Автоматическая очистка старых IP.
    """
    def __init__(self):
        self.requests: dict[str, list[float]] = defaultdict(list)
        self.locks: dict[str, asyncio.Lock] = {}
        self._cleanup_lock = asyncio.Lock()
        self._last_cleanup = time.monotonic()

    async def acquire(self, client_ip: str) -> bool:
        """Атомарная проверка и добавление запроса. True если лимит не превышен."""
        lock = self.locks.setdefault(client_ip, asyncio.Lock())

        async with lock:
            now = time.monotonic()
            window_start = now - RATE_LIMIT_WINDOW

            self.requests[client_ip] = [
                t for t in self.requests[client_ip] if t > window_start
            ]

            if len(self.requests[client_ip]) >= RATE_LIMIT_REQUESTS:
                return False

            self.requests[client_ip].append(now)

        await self._maybe_cleanup(now)

        return True

    async def _maybe_cleanup(self, now: float):
        """Удаляет IP, по которым не было запросов более 10 минут."""
        if now - self._last_cleanup < 300:
            return

        async with self._cleanup_lock:
            if now - self._last_cleanup < 300:
                return

            stale_ips = []
            for ip, timestamps in self.requests.items():
                if not timestamps or timestamps[-1] < now - 600:
                    stale_ips.append(ip)

            for ip in stale_ips:
                self.requests.pop(ip, None)
                self.locks.pop(ip, None)

            self._last_cleanup = now

            if stale_ips:
                logger.debug(f"Rate limiter cleanup: removed {len(stale_ips)} stale IPs")


rate_limiter = RateLimiter()

# ==================== MIDDLEWARE ====================

class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            client_ip = request.client.host if request.client else "unknown"

            # Healthcheck — без ключа
            if request.url.path == "/health":
                response = await call_next(request)
                return response

            # 🔐 1. Проверяем API ключ
            api_key = request.headers.get("X-API-Key")
            if not api_key:
                api_key = request.query_params.get("apikey")

            if not api_key or not hmac.compare_digest(api_key, PROXY_API_KEY):
                return JSONResponse(
                    content={"error": "Not found"},
                    status_code=404
                )

            # 🔐 2. Rate limit
            if RATE_LIMIT_ENABLED:
                allowed = await rate_limiter.acquire(client_ip)
                if not allowed:
                    logger.warning(f"Rate limit exceeded: {client_ip}")
                    return JSONResponse(
                        content={"error": "Not found"},
                        status_code=404
                    )

            # 🔐 3. Проверяем путь
            path = request.url.path
            is_allowed = False

            parts = path.strip("/").split("/")

            if len(parts) == 1 and parts[0]:
                is_allowed = True
            elif len(parts) == 6:
                if parts[1:] == ["api", "v2.0", "indexers", "all", "results"]:
                    is_allowed = True

            if not is_allowed:
                return JSONResponse(
                    content={"error": "Not found"},
                    status_code=404
                )

            # 🔐 4. Всё ок
            response = await call_next(request)

            response.headers.update({
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "DENY",
                "Cache-Control": "no-store",
            })

            if "server" in response.headers:
                del response.headers["server"]

            logger.debug(f"✅ {request.method} {path} from {client_ip}")

            return response

        except Exception:
            logger.exception("Security middleware error")
            return JSONResponse(
                content={"error": "Not found"},
                status_code=404
            )


# ==================== ОСНОВНАЯ ФУНКЦИЯ ====================

def add_security(app: FastAPI) -> FastAPI:
    app.add_middleware(SecurityMiddleware)
    app.docs_url = None
    app.redoc_url = None
    app.openapi_url = None

    logger.info("=" * 60)
    logger.info("🔒 SECURITY MIDDLEWARE LOADED (prod)")
    logger.info(f"API key: ✅ SET ({len(PROXY_API_KEY)} chars)")
    logger.info(f"Rate limiting: {'✅ ON' if RATE_LIMIT_ENABLED else '⚠️ OFF'}")
    if RATE_LIMIT_ENABLED:
        logger.info(f"Limit: {RATE_LIMIT_REQUESTS} req/{RATE_LIMIT_WINDOW}s per IP")
        logger.info("Isolation: separate lock per IP")
        logger.info("Cleanup: stale IPs removed every 5 min")
    logger.info("Healthcheck: /health (no auth)")
    logger.info("=" * 60)

    return app
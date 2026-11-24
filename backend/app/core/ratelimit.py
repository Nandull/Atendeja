"""Limite de requisições em memória para as rotas públicas (sem login).

Janela deslizante por chave (ex.: IP + ação). Serve para um servidor só,
que é o cenário do MVP. Com várias instâncias da API, trocar por Redis
mantendo a mesma interface.
"""

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from app.core.config import get_settings


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int, window_s: int) -> bool:
        """Registra uma tentativa. Devolve False se passou do limite."""
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= now - window_s:
                hits.popleft()
            if len(hits) >= limit:
                return False
            hits.append(now)
            if len(self._hits) > 50_000:  # evita crescer sem fim
                self._prune(now, window_s)
            return True

    def _prune(self, now: float, window_s: int) -> None:
        for key in [k for k, v in self._hits.items() if not v or v[-1] <= now - window_s]:
            del self._hits[key]

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = RateLimiter()


def client_ip(request: Request) -> str:
    if get_settings().trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "desconhecido"


def enforce(request: Request, action: str, limit: int, window_s: int) -> None:
    if not limiter.hit(f"{action}:{client_ip(request)}", limit, window_s):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Muitas tentativas em pouco tempo. Aguarde alguns minutos.",
        )

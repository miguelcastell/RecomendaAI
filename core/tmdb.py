"""Cliente TMDB — capas de pôster e resolução de títulos (Letterboxd).

Credenciais lidas de variáveis de ambiente (carregadas de `.env` se presente):
  - TMDB_API_TOKEN  → "API Read Access Token" (v4), enviado como `Bearer` (preferido).
  - TMDB_API_KEY    → chave (v3), usada como fallback via `?api_key=`.

Caches persistentes em `data/tmdb_cache/` (JSON), para nunca repetir uma chamada:
  - posters.json:  "tmdb_id" -> poster_path  ("" = filme sem pôster)
  - search.json:   "nome|ano" -> tmdb_id     (null = nada encontrado)

Tudo degrada com elegância: sem credenciais (ou sem rede), as funções devolvem
`None` e o resto do sistema cai para placeholder / casamento fuzzy.
"""

from __future__ import annotations

import atexit
import json
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Iterable, Optional

import requests

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# --------------------------------------------------------------------------
# .env (loader minimalista, sem dependência externa)
# --------------------------------------------------------------------------
def _load_dotenv(path: str) -> None:
    if not os.path.exists(path):
        return
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                # `setdefault`: variável de ambiente real tem prioridade sobre o .env.
                os.environ.setdefault(key, val)
    except OSError:
        pass


_load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

TMDB_API_TOKEN = os.environ.get("TMDB_API_TOKEN", "").strip()
TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "").strip()
TMDB_LANG = os.environ.get("TMDB_LANG", "pt-BR").strip()

_API_BASE = "https://api.themoviedb.org/3"
IMAGE_BASE = "https://image.tmdb.org/t/p/w342"


def is_configured() -> bool:
    """True se há ao menos uma credencial (token v4 ou chave v3)."""
    return bool(TMDB_API_TOKEN or TMDB_API_KEY)


# --------------------------------------------------------------------------
# Sessão HTTP (uma por processo, com keep-alive)
# --------------------------------------------------------------------------
_session: Optional[requests.Session] = None
_session_lock = threading.Lock()


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        with _session_lock:
            if _session is None:
                s = requests.Session()
                s.headers.update({"accept": "application/json"})
                if TMDB_API_TOKEN:
                    s.headers.update({"Authorization": f"Bearer {TMDB_API_TOKEN}"})
                _session = s
    return _session


def _params(extra: Optional[dict] = None) -> dict:
    p = dict(extra or {})
    # Token v4 vai no header; só mandamos api_key (v3) se não houver token.
    if not TMDB_API_TOKEN and TMDB_API_KEY:
        p["api_key"] = TMDB_API_KEY
    return p


def _get(path: str, params: Optional[dict] = None, timeout: float = 10.0) -> Optional[dict]:
    if not is_configured():
        return None
    try:
        resp = _get_session().get(f"{_API_BASE}{path}", params=_params(params), timeout=timeout)
        if resp.status_code == 200:
            return resp.json()
    except (requests.RequestException, ValueError):
        return None
    return None


# --------------------------------------------------------------------------
# Cache JSON persistente (thread-safe, escrita atômica)
# --------------------------------------------------------------------------
class _JsonCache:
    def __init__(self, path: str, flush_every: int = 30):
        self.path = path
        self.flush_every = flush_every
        self._lock = threading.Lock()
        self._dirty = 0
        self.data: dict = {}
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    self.data = json.load(f)
            except (OSError, ValueError):
                self.data = {}

    def __contains__(self, key: str) -> bool:
        return key in self.data

    def get(self, key: str, default=None):
        return self.data.get(key, default)

    def set(self, key: str, value) -> None:
        with self._lock:
            self.data[key] = value
            self._dirty += 1
            if self._dirty >= self.flush_every:
                self._flush_locked()

    def flush(self) -> None:
        with self._lock:
            self._flush_locked()

    def _flush_locked(self) -> None:
        if self._dirty == 0 and os.path.exists(self.path):
            return
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = f"{self.path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False)
        os.replace(tmp, self.path)
        self._dirty = 0


_CACHE_DIR = os.path.join(_PROJECT_ROOT, "data", "tmdb_cache")
_poster_cache = _JsonCache(os.path.join(_CACHE_DIR, "posters.json"))
_search_cache = _JsonCache(os.path.join(_CACHE_DIR, "search.json"))


@atexit.register
def _flush_all() -> None:
    _poster_cache.flush()
    _search_cache.flush()


# --------------------------------------------------------------------------
# Pôsteres
# --------------------------------------------------------------------------
def poster_path(tmdb_id: int) -> Optional[str]:
    """`poster_path` do filme (ex.: "/abc.jpg"), ou None. Cacheado em disco."""
    key = str(int(tmdb_id))
    if key in _poster_cache:
        return _poster_cache.get(key) or None
    data = _get(f"/movie/{int(tmdb_id)}", {"language": TMDB_LANG})
    pp = (data or {}).get("poster_path") or ""
    _poster_cache.set(key, pp)
    return pp or None


def poster_url(tmdb_id: int) -> Optional[str]:
    """URL completa do pôster (w342), ou None."""
    pp = poster_path(tmdb_id)
    return f"{IMAGE_BASE}{pp}" if pp else None


def prefetch_posters(ids: Iterable[int], max_workers: int = 16) -> None:
    """Aquece o cache de pôsteres de vários filmes em paralelo (apenas os ausentes)."""
    if not is_configured():
        return
    missing = []
    seen = set()
    for i in ids:
        try:
            tid = int(i)
        except (TypeError, ValueError):
            continue
        if tid <= 0 or tid in seen or str(tid) in _poster_cache:
            continue
        seen.add(tid)
        missing.append(tid)
    if not missing:
        return
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        list(ex.map(poster_path, missing))
    _poster_cache.flush()


# --------------------------------------------------------------------------
# Busca / resolução de título → tmdb_id (para o import do Letterboxd)
# --------------------------------------------------------------------------
def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _pick_best(results: list, name: str, year: Optional[int]) -> Optional[int]:
    """Escolhe o melhor candidato do `/search/movie`.

    Com filtro de ano o TMDB **não** ordena por popularidade, então `results[0]`
    erra (ex.: "Parasite" 2019 traz um curta obscuro antes do filme real). Ranqueia
    por: título exato → ano exato → popularidade → nº de votos.
    """
    if not results:
        return None
    nq = _norm(name)

    def score(r: dict) -> tuple:
        exact = 1 if nq in (_norm(r.get("title")), _norm(r.get("original_title"))) else 0
        ry = (r.get("release_date") or "")[:4]
        year_ok = 1 if (year and ry == str(year)) else 0
        pop = float(r.get("popularity") or 0.0)
        votes = int(r.get("vote_count") or 0)
        return (exact, year_ok, pop, votes)

    best = max(results, key=score)
    return int(best["id"])


def search_movie_id(name: str, year: Optional[int] = None) -> Optional[int]:
    """Resolve (nome, ano) para um tmdb_id via `/search/movie`. Cacheado.

    Sem `language` na busca: o `title` volta no idioma original (o `Name` do
    Letterboxd é em inglês), o que ajuda o casamento exato de título.
    """
    name = (name or "").strip()
    if not name:
        return None
    key = f"{_norm(name)}|{year or ''}"
    if key in _search_cache:
        v = _search_cache.get(key)
        return int(v) if v is not None else None
    params = {"query": name, "include_adult": "false"}
    if year:
        params["year"] = int(year)
    data = _get("/search/movie", params)
    results = (data or {}).get("results") or []
    tid = _pick_best(results, name, year)
    _search_cache.set(key, tid)
    return tid


def prefetch_search(items: Iterable[tuple], max_workers: int = 16) -> None:
    """Aquece o cache de busca de vários (nome, ano) em paralelo (só os ausentes)."""
    if not is_configured():
        return
    todo = []
    seen = set()
    for name, year in items:
        key = f"{_norm(name)}|{year or ''}"
        if key in seen or key in _search_cache:
            continue
        seen.add(key)
        todo.append((name, year))
    if not todo:
        return
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        list(ex.map(lambda t: search_movie_id(t[0], t[1]), todo))
    _search_cache.flush()

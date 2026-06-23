"""Pôsteres — busca URL do poster do TMDB.

Tenta primeiro resolver do JSON (data/tmdb_movies_large.json). Se não achar,
cai para o placeholder com o título.
"""

from __future__ import annotations

import os
from typing import Optional
from urllib.parse import quote

_PLACEHOLDER_BASE = "https://placehold.co/342x513/141414/e50914"
_TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w342"


def _find_poster_in_json(tmdb_id: int) -> Optional[str]:
    """Procura o poster_path no JSON (tmdb_movies_large.json ou tmdb_movies.json)."""
    import json

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for fname in ["tmdb_movies_large.json", "tmdb_movies.json"]:
        path = os.path.join(project_root, "data", fname)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    movies = json.load(f)
                for m in movies:
                    if int(m.get("id", 0)) == tmdb_id:
                        pp = m.get("poster_path")
                        if pp:
                            return f"{_TMDB_IMAGE_BASE}{pp}"
            except Exception:
                pass
    return None


def get_poster(tmdb_id: int, title: Optional[str] = None) -> str:
    """Retorna URL do pôster do filme (ou placeholder)."""
    if tmdb_id and tmdb_id > 0:
        poster_url = _find_poster_in_json(tmdb_id)
        if poster_url:
            return poster_url
    text = quote((title or "Sem pôster")[:40])
    return f"{_PLACEHOLDER_BASE}?text={text}"

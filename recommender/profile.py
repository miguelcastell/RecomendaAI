"""Perfil de gosto a partir do Letterboxd — traça o perfil e recomenda por conteúdo.

O colaborativo (fold-in sobre fatores do MovieLens) sozinho traça mal um gosto
refinado: para um fã de Hitchcock/Kubrick/Coppola ele sugeria *Jogos Mortais* e
*Transformers*. Aqui usamos o que o catálogo tem de mais forte — os **embeddings
e5-large** dos filmes — para montar um **vetor de gosto** a partir dos filmes que
a pessoa amou (ponderado pela nota e, opcionalmente, enriquecido pelas resenhas),
e recomendamos "mais como isso". Também devolvemos um **resumo do perfil**
(gêneros, diretores, atores, décadas, temas) e fundimos com o colaborativo para
não perder serendipidade.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Optional

import numpy as np

from core import catalog

LIKE_THRESHOLD = 3.5      # nota >= isto conta como "gostou" (escala 0.5–5.0)
REVIEW_BLEND = 0.25       # quanto a resenha (o que a pessoa articula) entra no vetor
CONTENT_RRF_W = 1.0       # peso do conteúdo no blend final
COLLAB_RRF_W = 0.5        # peso do colaborativo no blend final
RRF_K = 20


def _norm(v: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(v))
    return v / n if n > 0 else v


def _weight(rating: float) -> float:
    """Peso do filme no perfil: 5★→2.0, 4★→1.0, 3.5★→0.5, abaixo disso 0."""
    return max(0.0, float(rating) - 3.0)


class TasteProfile:
    def __init__(self, engine, detail: list[dict]):
        self.engine = engine
        self.detail = detail
        self.seen = {int(d["tmdb_id"]) for d in detail}
        self.liked = [d for d in detail if float(d["rating"]) >= LIKE_THRESHOLD]
        self.taste_syn: Optional[np.ndarray] = None
        self.taste_kw: Optional[np.ndarray] = None
        self._build_vectors()

    # ----------------------------------------------------------- vetor de gosto
    def _build_vectors(self) -> None:
        eng = self.engine
        if eng._embeddings is None:
            return
        rows, weights = [], []
        for d in self.liked:
            r = eng._row_index.get(int(d["tmdb_id"]))
            if r is not None:
                rows.append(r)
                weights.append(_weight(d["rating"]) or 0.5)
        if not rows:
            return
        w = np.asarray(weights, dtype=np.float64)[:, None]
        self.taste_syn = _norm((eng._embeddings[rows].astype(np.float64) * w).sum(0))
        if eng._kw_embeddings is not None:
            self.taste_kw = _norm((eng._kw_embeddings[rows].astype(np.float64) * w).sum(0))

        # Resenhas: o que a pessoa articula gostar (tom, temas). Embute e mistura.
        reviews = [(d.get("review") or "", _weight(d["rating"]) or 0.5)
                   for d in self.liked if (d.get("review") or "").strip()]
        if reviews and REVIEW_BLEND > 0 and self.taste_syn is not None:
            rv = np.asarray([eng._encode(t[:512]) for t, _ in reviews], dtype=np.float64)
            rw = np.asarray([w for _, w in reviews])[:, None]
            rev_vec = _norm((rv * rw).sum(0))
            self.taste_syn = _norm((1 - REVIEW_BLEND) * self.taste_syn + REVIEW_BLEND * rev_vec)

    @property
    def has_vector(self) -> bool:
        return self.taste_syn is not None

    def content_scores(self) -> np.ndarray:
        """Score de conteúdo (cosseno do filme ao vetor de gosto) para todo o catálogo."""
        eng = self.engine
        s = eng._embeddings @ self.taste_syn
        if self.taste_kw is not None and eng._kw_embeddings is not None:
            s = s + (eng._kw_embeddings @ self.taste_kw)
        return s

    def recommend_content(self, n: int, exclude: Optional[set] = None) -> list[tuple[int, float]]:
        eng = self.engine
        if not self.has_vector:
            return []
        skip = set(exclude or set()) | self.seen
        scores = self.content_scores()
        out: list[tuple[int, float]] = []
        for i in np.argsort(scores)[::-1]:
            tid = int(eng._movie_ids[i])
            if tid in skip:
                continue
            out.append((tid, float(scores[i])))
            if len(out) >= n:
                break
        return out

    # --------------------------------------------------------------- resumo do perfil
    def summary(self, top: int = 6) -> dict[str, Any]:
        cat = catalog.get_catalog()
        g, d, a, k = (defaultdict(float) for _ in range(4))
        dec: dict[int, float] = defaultdict(float)
        for item in self.liked:
            tid = int(item["tmdb_id"])
            w = _weight(item["rating"]) or 0.5
            for name in catalog.get_movie_genres(tid):
                g[name] += w
            for name in catalog.get_movie_keywords(tid):
                k[name] += w
            for p in catalog.get_movie_people(tid, role="director"):
                d[p["name"]] += w
            for p in catalog.get_movie_people(tid, role="actor")[:5]:
                a[p["name"]] += w
            year = cat.get(tid, {}).get("release_year")
            if year:
                dec[(int(year) // 10) * 10] += w
        topn = lambda dd: [name for name, _ in sorted(dd.items(), key=lambda kv: -kv[1])[:top]]
        ratings = [float(x["rating"]) for x in self.detail]
        return {
            "n_rated": len(self.detail),
            "n_liked": len(self.liked),
            "avg_rating": round(float(np.mean(ratings)), 2) if ratings else None,
            "genres": topn(g),
            "directors": topn(d),
            "actors": topn(a),
            "themes": topn(k),
            "decades": [f"{int(x)}s" for x in sorted(dec, key=lambda x: -dec[x])[:4]],
        }

    # ----------------------------------------------------- explicação por filme
    def _why(self, tmdb_id: int, summary: dict) -> list[str]:
        """Por que recomendamos: interseção com gêneros/diretores favoritos."""
        reasons = []
        dirs = {p["name"] for p in catalog.get_movie_people(tmdb_id, role="director")}
        shared_dir = [x for x in summary["directors"] if x in dirs]
        if shared_dir:
            reasons.append(f"direção de {shared_dir[0]}")
        gset = set(catalog.get_movie_genres(tmdb_id))
        shared_g = [x for x in summary["genres"] if x in gset]
        if shared_g:
            reasons.append(" / ".join(shared_g[:2]))
        return reasons


def recommend_from_profile(detail: list[dict], n: int = 20) -> dict[str, Any]:
    """Recomenda combinando conteúdo (vetor de gosto) + colaborativo, e devolve o
    perfil traçado. `detail`: [{tmdb_id, rating, name, year, review}]."""
    from retrieval.search_engine import get_engine

    engine = get_engine()
    prof = TasteProfile(engine, detail)
    summary = prof.summary()

    content = prof.recommend_content(n * 3)

    # Colaborativo (serendipidade) — best-effort.
    collab: list[dict] = []
    try:
        from recommender.collaborative import get_recommender
        rated = [(d["tmdb_id"], d["rating"]) for d in detail]
        collab = get_recommender().recommend(rated, n=n * 3)
    except Exception:
        collab = []

    # Fusão por rank recíproco (RRF): conteúdo manda, colaborativo complementa.
    score: dict[int, float] = defaultdict(float)
    for i, (tid, _s) in enumerate(content):
        score[tid] += CONTENT_RRF_W / (RRF_K + i)
    for i, r in enumerate(collab):
        score[int(r["tmdb_id"])] += COLLAB_RRF_W / (RRF_K + i)

    cat = catalog.get_catalog()
    ranked = sorted((t for t in score if t not in prof.seen),
                    key=lambda t: -score[t])[:n]

    recs = []
    for tid in ranked:
        mv = cat.get(tid, {})
        recs.append({
            "tmdb_id": int(tid),
            "title": mv.get("title"),
            "release_year": mv.get("release_year"),
            "vote_average": mv.get("vote_average"),
            "overview": (mv.get("overview") or "")[:240],
            "why": prof._why(tid, summary),
            "method": "perfil (conteúdo+colaborativo)",
        })
    return {"profile": summary, "recommendations": recs}

"""Recuperação de filmes — achar um filme que o usuário conhece mas não lembra.

Sistema **independente** da recomendação (não usa ratings). Modos combináveis:
  - nome fuzzy (rapidfuzz sobre títulos)
  - sinopse híbrida (TF-IDF PT + embeddings multilíngues, scores fundidos)
  - pessoa (ator/diretor via movie_people)
  - keyword/tema (via movie_keywords)
Com filtros opcionais de ano, gênero e idioma.

O índice de sinopse é gerado por `retrieval/index_builder.py`. Se ele não
existir, a busca por sinopse degrada graciosamente (TF-IDF only, ou indisponível),
mas nome/pessoa/keyword continuam funcionando.
"""

from __future__ import annotations

import os
import re
from typing import Any, Optional

import numpy as np

from core import catalog, db
from retrieval import index_builder as ib

# Artigos PT iniciais: ruído no casamento de nome ("O pescotapa" casava todo
# "O ..."). Removidos antes do fuzzy, dos dois lados (consulta e título).
_PT_ARTICLES = {"o", "a", "os", "as", "um", "uma", "uns", "umas"}


def _name_key(s: str) -> str:
    """Normaliza um título/consulta p/ casamento de nome: minúsculas + remove o
    artigo inicial ('O Psicopata Americano' ~ 'Psicopata Americano')."""
    toks = (s or "").lower().split()
    if toks and toks[0] in _PT_ARTICLES:
        toks = toks[1:]
    return " ".join(toks)


def _name_score(query_key: str, title: str) -> float:
    """Score de nome (0–1+): WRatio (tolera typo/partial) com **penalização de
    cobertura** que derruba títulos muito mais curtos que a consulta — mata o
    ruído de fragmento ("Amer" p/ "amerecano", "O Clube" p/ "clube da luat") sem
    punir títulos mais longos ("Matrix Reloaded" p/ "matrix"). Bônus exato/prefixo."""
    from rapidfuzz import fuzz

    tk = _name_key(title)
    base = fuzz.WRatio(query_key, tk) / 100.0
    if tk == query_key:
        return base + 0.5
    if tk and tk.startswith(query_key):
        return base + 0.15
    coverage = min(1.0, len(tk) / max(len(query_key), 1))
    return base * (0.4 + 0.6 * coverage)


# Rótulos dos sinais para a explicação exibida ao usuário.
SIGNAL_LABELS = {
    "lexical": "termos da sinopse",
    "synopsis": "sentido da sinopse",
    "keyword": "tema",
    "name": "nome",
}

# Pesos default da fusão na busca por sinopse: TF-IDF + embedding da sinopse +
# embedding temático (keywords/gêneros). O embedding da sinopse é o sinal mais
# confiável no caso geral; o lexical (TF-IDF) resgata enredos com termos próprios
# ("sete pecados capitais", "revivendo o mesmo dia") e o temático resgata casos
# de conceito ("time loop", "memory loss") que a sinopse sozinha não pega.
DEFAULT_LEXICAL_WEIGHT = 0.25
DEFAULT_EMBED_WEIGHT = 0.5
DEFAULT_KEYWORD_WEIGHT = 0.45

# Re-ranker cross-encoder (2º estágio): reordena o top-K da 1ª etapa misturando
# o score do cross-encoder com o da recuperação (blend) como prior estabilizador.
# Medido no harness de 52 casos: MRR 0.506→0.577, hits@10 39→43.
RERANK_POOL = int(os.environ.get("RECOMENDAI_RERANK_POOL", "50"))
RERANK_BLEND = float(os.environ.get("RECOMENDAI_RERANK_BLEND", "0.3"))
RERANK_ENABLED = os.environ.get("RECOMENDAI_RERANK", "1").lower() not in ("0", "false", "no")


def _zscore(x: np.ndarray) -> np.ndarray:
    """Padroniza um vetor de scores (média 0, desvio 1).

    Fundir por z-score em vez de min-max+soma tem duas vantagens medidas no
    harness: (1) é robusto a outliers — um único filme com score altíssimo não
    achata todos os outros perto de zero; (2) preserva o quanto um sinal
    *separa* um filme da média, então um enredo com termo próprio muito forte
    (lexical) ou um tema muito específico (keywords) é resgatado mesmo quando o
    embedding da sinopse é fraco para aquela consulta."""
    if x.size == 0:
        return x
    std = float(x.std())
    if std <= 0:
        return np.zeros_like(x)
    return (x - float(x.mean())) / std


class SearchEngine:
    """Motor de recuperação. Carrega catálogo + índice de sinopse (se houver)."""

    def __init__(self, load_embeddings: bool = True, rerank: bool = RERANK_ENABLED):
        self.catalog = catalog.get_catalog()  # {tmdb_id: filme}
        # Títulos para fuzzy (lista paralela id<->título).
        self._title_ids: list[int] = []
        self._titles: list[str] = []
        for tid, mv in self.catalog.items():
            self._title_ids.append(tid)
            self._titles.append(mv["title"] or "")

        # Índice de sinopse (carregado sob demanda / no init se existir).
        self._movie_ids: Optional[np.ndarray] = None      # ordem das linhas
        self._bm25 = None                                  # BM25Index (sinal lexical)
        self._embeddings: Optional[np.ndarray] = None      # N×D sinopse (L2-norm)
        self._kw_embeddings: Optional[np.ndarray] = None   # N×D temático (L2-norm)
        self._kw_term_emb: Optional[np.ndarray] = None     # Nkw×D por keyword (L2-norm)
        self._kw_term_row: dict[str, int] = {}             # nome(lower) -> linha em _kw_term_emb
        self._embed_model = None
        self._embed_model_name: Optional[str] = None
        self._query_emb_cache: dict[str, np.ndarray] = {}
        self._load_embeddings = load_embeddings
        # Re-ranker cross-encoder (2º estágio), carregado sob demanda.
        self.rerank_enabled = rerank
        self._reranker = None
        self._reranker_failed = False
        # Query-SLM opcional (tradução PT→EN p/ o sinal de keyword), off por padrão.
        from retrieval.query_expander import QUERY_SLM_ENABLED
        self.query_slm_enabled = QUERY_SLM_ENABLED
        self._query_expander = None
        self._query_expander_failed = False
        self._load_index()

        # tmdb_id -> linha em self._movie_ids (para ler scores de sinopse).
        self._row_index_cache: Optional[dict[int, int]] = None
        # Mapas reversos para pessoa/keyword (construídos sob demanda).
        self._person_movies: Optional[dict[int, list[int]]] = None
        self._keyword_movies: Optional[dict[int, list[int]]] = None
        self._people_names: Optional[list[tuple[int, str]]] = None
        self._keyword_names: Optional[list[tuple[int, str]]] = None

    # ------------------------------------------------------------------ índice
    def _load_index(self) -> None:
        if not os.path.exists(ib.META_PATH):
            return
        import json

        with open(ib.META_PATH, encoding="utf-8") as f:
            meta = json.load(f)
        self._movie_ids = np.load(ib.MOVIE_IDS_PATH)
        from retrieval.bm25 import BM25Index

        self._bm25 = BM25Index.load(
            ib.BM25_VECTORIZER_PATH, ib.BM25_COUNTS_PATH,
            k1=meta.get("bm25_k1", 1.5), b=meta.get("bm25_b", 0.75),
        )
        if self._load_embeddings and meta.get("has_embeddings") and os.path.exists(ib.EMBEDDINGS_PATH):
            self._embeddings = np.load(ib.EMBEDDINGS_PATH)
            self._embed_model_name = meta.get("embed_model")
            if meta.get("has_keyword_embeddings") and os.path.exists(ib.KW_EMBEDDINGS_PATH):
                self._kw_embeddings = np.load(ib.KW_EMBEDDINGS_PATH)
            if meta.get("has_keyword_terms") and os.path.exists(ib.KEYWORD_TERM_EMB_PATH):
                self._kw_term_emb = np.load(ib.KEYWORD_TERM_EMB_PATH)
                with open(ib.KEYWORD_TERMS_PATH, encoding="utf-8") as f:
                    names = json.load(f)
                self._kw_term_row = {nm.lower(): i for i, nm in enumerate(names)}

    @property
    def has_synopsis_index(self) -> bool:
        return self._bm25 is not None

    def _get_embed_model(self):
        if self._embed_model is None:
            from sentence_transformers import SentenceTransformer

            from core.device import get_device

            self._embed_model = SentenceTransformer(
                self._embed_model_name or ib.DEFAULT_EMBED_MODEL, device=get_device()
            )
        return self._embed_model

    def _get_reranker(self):
        """Carrega o cross-encoder sob demanda; desativa em silêncio se falhar."""
        if not self.rerank_enabled or self._reranker_failed:
            return None
        if self._reranker is None:
            try:
                from retrieval.reranker import CrossEncoderReranker

                self._reranker = CrossEncoderReranker()
            except Exception:
                self._reranker_failed = True
                return None
        return self._reranker

    def _get_query_expander(self):
        """Query-SLM (tradução) sob demanda; desativa em silêncio se falhar."""
        if not self.query_slm_enabled or self._query_expander_failed:
            return None
        if self._query_expander is None:
            try:
                from retrieval.query_expander import QueryExpander

                self._query_expander = QueryExpander()
            except Exception:
                self._query_expander_failed = True
                return None
        return self._query_expander

    def _keyword_query_emb(self, query: str, q_emb: np.ndarray) -> np.ndarray:
        """Embedding da consulta para o sinal de keyword. Com o query-SLM ligado,
        usa a tradução EN (keywords da TMDB são em inglês); senão, o embedding PT."""
        qx = self._get_query_expander()
        if qx is None:
            return q_emb
        try:
            return self._encode(qx.translate(query))
        except Exception:
            self._query_expander_failed = True
            return q_emb

    def _text_for(self, tmdb_id: int) -> str:
        """Passagem para o cross-encoder: a sinopse; se vazia, título + keywords."""
        mv = self.catalog.get(tmdb_id, {})
        overview = (mv.get("overview") or "").strip()
        if overview:
            return overview
        kws = " ".join(catalog.get_movie_keywords(tmdb_id)[:10])
        return f"{mv.get('title', '')} {kws}".strip()

    def _maybe_rerank(self, query: str, scored: list[tuple[int, float]], ctx: dict,
                      min_words: int = 4, pool: int = RERANK_POOL
                      ) -> list[tuple[int, float]]:
        """Reordena (com cross-encoder) o top-`pool` de `scored`, mantendo a cauda.
        Só age em consultas descritivas (>= `min_words` palavras) — para títulos
        curtos a 1ª etapa já é melhor."""
        rr = self._get_reranker()
        if rr is None or len(scored) < 2 or len(query.split()) < min_words:
            return scored
        head = scored[:pool]
        retr = {tid: s for tid, s in head}
        try:
            reordered = rr.rerank(query, [t for t, _ in head], self._text_for,
                                  retr_scores=retr, blend=RERANK_BLEND)
        except Exception:
            self._reranker_failed = True
            return scored
        ctx["reranked"] = True
        return reordered + scored[pool:]

    def _encode(self, query: str) -> np.ndarray:
        """Embedding L2-normalizado da consulta (cacheado por string de consulta)."""
        cached = self._query_emb_cache.get(query)
        if cached is None:
            cached = self._get_embed_model().encode(
                [query], normalize_embeddings=True, convert_to_numpy=True
            ).astype(np.float32)[0]
            self._query_emb_cache[query] = cached
        return cached

    # -------------------------------------------------------------- formatação
    def _format(self, tmdb_id: int, score: float) -> dict[str, Any]:
        mv = self.catalog.get(tmdb_id, {})
        overview = mv.get("overview", "") or ""
        return {
            "tmdb_id": int(tmdb_id),
            "title": mv.get("title"),
            "release_year": mv.get("release_year"),
            "original_language": mv.get("original_language"),
            "vote_average": mv.get("vote_average"),
            "overview": overview[:240],
            "score": round(float(score), 4),
        }

    # ------------------------------------------------------------------- filtros
    def _passes_filters(self, tmdb_id: int, filters: Optional[dict]) -> bool:
        if not filters:
            return True
        mv = self.catalog.get(tmdb_id)
        if mv is None:
            return False
        year = mv.get("release_year")
        if filters.get("year") is not None and year != filters["year"]:
            return False
        if filters.get("year_min") is not None and (year is None or year < filters["year_min"]):
            return False
        if filters.get("year_max") is not None and (year is None or year > filters["year_max"]):
            return False
        lang = filters.get("language")
        if lang is not None and (mv.get("original_language") or "").lower() != lang.lower():
            return False
        genre = filters.get("genre")
        if genre is not None:
            gset = {g.lower() for g in catalog.get_movie_genres(tmdb_id)}
            if genre.lower() not in gset:
                return False
        return True

    # =================================================================== modos
    def search_by_name(self, query: str, n: int = 10, score_cutoff: float = 50.0
                       ) -> list[tuple[int, float]]:
        """Nome fuzzy via rapidfuzz (erro de digitação / nome parcial).

        `processor=str.lower` torna o casamento case-insensitive (sem isso o
        `WRatio` dava "matrix"→"Animatrix" 90 > "Matrix" exato 83). Além disso, um
        match **exato** ou de **prefixo** do título recebe um bônus, para que o
        título buscado vença substrings mais longas que o contêm."""
        from rapidfuzz import fuzz, process

        # Pré-seleção rápida por WRatio (sobre os 22k), depois re-pontua o topo com
        # `_name_score` (WRatio + penalização de cobertura + bônus exato/prefixo).
        results = process.extract(
            query, self._titles, scorer=fuzz.WRatio, processor=_name_key,
            limit=n * 8, score_cutoff=score_cutoff,
        )
        qk = _name_key(query)
        scored = [(self._title_ids[idx], _name_score(qk, self._titles[idx]))
                  for _title, _score, idx in results]
        scored.sort(key=lambda kv: kv[1], reverse=True)
        return scored[: n * 4]

    def _synopsis_components(self, query: str,
                            q_emb: Optional[np.ndarray] = None,
                            lexical_weight: float = DEFAULT_LEXICAL_WEIGHT,
                            embed_weight: float = DEFAULT_EMBED_WEIGHT,
                            keyword_weight: float = DEFAULT_KEYWORD_WEIGHT,
                            ) -> dict[str, np.ndarray]:
        """Contribuições **já ponderadas** de cada sinal de sinopse (alinhadas a
        `self._movie_ids`): BM25 (lexical), embedding da sinopse e embedding
        temático de keywords. Cada sinal é padronizado por z-score e multiplicado
        pelo seu peso, de modo que a soma das três é o score fundido.

        Devolver os componentes (em vez de só a soma) é o que permite explicar
        ao usuário quanto cada sinal pesou em cada resultado (Objetivo 1)."""
        if self._bm25 is None:
            raise RuntimeError(
                "Índice de sinopse ausente. Rode retrieval/index_builder.py "
                "(ou research/build_search_index.ipynb) primeiro."
            )
        n = self._bm25.n_docs
        lexical_scores = self._bm25.scores(query)
        comps = {
            "lexical": lexical_weight * _zscore(lexical_scores),
            "synopsis": np.zeros(n, dtype=np.float64),
            "keyword": np.zeros(n, dtype=np.float64),
        }
        if self._embeddings is not None and (embed_weight > 0 or keyword_weight > 0):
            if q_emb is None:
                q_emb = self._encode(query)
            if embed_weight > 0:
                comps["synopsis"] = embed_weight * _zscore(self._embeddings @ q_emb)
            if keyword_weight > 0 and self._kw_embeddings is not None:
                kw_q = self._keyword_query_emb(query, q_emb)
                comps["keyword"] = keyword_weight * _zscore(self._kw_embeddings @ kw_q)
        return comps

    def _synopsis_scores(self, query: str, **weights) -> np.ndarray:
        """Vetor de scores de sinopse fundido (soma das contribuições z-score)."""
        comps = self._synopsis_components(query, **weights)
        return comps["lexical"] + comps["synopsis"] + comps["keyword"]

    def search_by_synopsis(self, query: str, n: int = 10, **weights) -> list[tuple[int, float]]:
        """Sinopse híbrida sobre todo o catálogo (top n*4 candidatos)."""
        fused = self._synopsis_scores(query, **weights)
        top = np.argsort(fused)[::-1][: n * 4]
        return [(int(self._movie_ids[i]), float(fused[i])) for i in top if fused[i] > 0]

    def synopsis_ranked_ids(self, query: str, rerank: bool = True,
                            pool: int = RERANK_POOL) -> list[int]:
        """Ordem completa (todos os tmdb_ids) da busca por sinopse, opcionalmente
        com o re-ranker aplicado ao top-`pool`. Usado pelo harness para medir a
        posição de qualquer alvo (mesmo fora do pool reordenado)."""
        fused = self._synopsis_scores(query)
        order = np.argsort(fused)[::-1]
        ids = [int(self._movie_ids[i]) for i in order]
        rr = self._get_reranker() if rerank else None
        if rr is not None and len(ids) > 1:
            retr = {ids[i]: float(fused[order[i]]) for i in range(min(pool, len(ids)))}
            try:
                reordered = rr.rerank(query, ids[:pool], self._text_for,
                                      retr_scores=retr, blend=RERANK_BLEND)
                ids = [t for t, _ in reordered] + ids[pool:]
            except Exception:
                self._reranker_failed = True
        return ids

    def _build_person_maps(self) -> None:
        person_movies: dict[int, list[int]] = {}
        for r in db.iter_query("SELECT person_id, tmdb_id FROM movie_people"):
            person_movies.setdefault(r["person_id"], []).append(r["tmdb_id"])
        self._person_movies = person_movies
        self._people_names = [
            (r["person_id"], r["name"]) for r in db.query("SELECT person_id, name FROM people")
        ]

    def search_by_person(self, query: str, n: int = 10, role: Optional[str] = None,
                         score_cutoff: float = 80.0) -> list[tuple[int, float]]:
        """Ator/diretor: casa o nome (fuzzy) e agrega os filmes da pessoa."""
        from rapidfuzz import fuzz, process

        if self._person_movies is None:
            self._build_person_maps()

        names = [name for _pid, name in self._people_names]
        matches = process.extract(
            query, names, scorer=fuzz.WRatio, limit=15, score_cutoff=score_cutoff
        )
        if not matches:
            return []

        # Pontua cada filme pela melhor correspondência de nome da pessoa.
        movie_score: dict[int, float] = {}
        movie_order: dict[int, int] = {}
        for _name, score, idx in matches:
            pid = self._people_names[idx][0]
            for tmdb_id in self._person_movies.get(pid, []):
                if role is not None and not self._has_role(tmdb_id, pid, role):
                    continue
                s = score / 100.0
                if s > movie_score.get(tmdb_id, 0.0):
                    movie_score[tmdb_id] = s
        # Desempate por popularidade.
        ranked = sorted(
            movie_score.items(),
            key=lambda kv: (kv[1], self.catalog.get(kv[0], {}).get("popularity") or 0.0),
            reverse=True,
        )
        return [(tid, s) for tid, s in ranked[: n * 4]]

    def _has_role(self, tmdb_id: int, person_id: int, role: str) -> bool:
        return db.query_scalar(
            "SELECT 1 FROM movie_people WHERE tmdb_id=? AND person_id=? AND role=? LIMIT 1",
            (tmdb_id, person_id, role),
        ) is not None

    def _build_keyword_maps(self) -> None:
        keyword_movies: dict[int, list[int]] = {}
        for r in db.iter_query("SELECT keyword_id, tmdb_id FROM movie_keywords"):
            keyword_movies.setdefault(r["keyword_id"], []).append(r["tmdb_id"])
        self._keyword_movies = keyword_movies
        self._keyword_names = [
            (r["keyword_id"], r["name"]) for r in db.query("SELECT keyword_id, name FROM keywords")
        ]

    def search_by_keyword(self, query: str, n: int = 10, score_cutoff: float = 80.0
                         ) -> list[tuple[int, float]]:
        """Tema/keyword: casa a keyword (fuzzy) e agrega os filmes."""
        from rapidfuzz import fuzz, process

        if self._keyword_movies is None:
            self._build_keyword_maps()

        names = [name for _kid, name in self._keyword_names]
        matches = process.extract(
            query, names, scorer=fuzz.WRatio, limit=15, score_cutoff=score_cutoff
        )
        if not matches:
            return []

        movie_score: dict[int, float] = {}
        for _name, score, idx in matches:
            kid = self._keyword_names[idx][0]
            for tmdb_id in self._keyword_movies.get(kid, []):
                s = score / 100.0
                movie_score[tmdb_id] = movie_score.get(tmdb_id, 0.0) + s
        ranked = sorted(
            movie_score.items(),
            key=lambda kv: (kv[1], self.catalog.get(kv[0], {}).get("popularity") or 0.0),
            reverse=True,
        )
        return [(tid, s) for tid, s in ranked[: n * 4]]

    # --------------------------------------------------------------- explicação
    def _relevance(self, score: float, lo: float, hi: float) -> int:
        """Relevância apresentável (0–100), min-max dentro do conjunto retornado.
        É relativa à busca (não comparável entre buscas) — por isso a **posição**
        também é exibida."""
        if hi <= lo:
            return 100
        return int(round(100.0 * (score - lo) / (hi - lo)))

    def _signal_contributions(self, tmdb_id: int, ctx: dict) -> dict[str, float]:
        """Contribuição (já ponderada) de cada sinal para o score deste filme.

        Quando o ranking mistura nome + sinopse (auto/combinada), a sinopse entra
        normalizada a [0,1] (`syn_norm`) para ser comparável ao nome; aqui a
        contribuição total da sinopse (`syn_w * syn_norm`) é repartida entre os
        três sub-sinais pela proporção positiva dos seus z-scores — assim as
        contribuições somam ao score real e ainda mostram o detalhamento."""
        raw: dict[str, float] = {}
        comps = ctx.get("comps")
        syn_w = ctx.get("syn_w", 1.0)
        syn_norm = ctx.get("syn_norm")  # dict tid->[0,1] quando há blend com nome
        row = self._row_index.get(int(tmdb_id)) if comps is not None else None
        if comps is not None and row is not None:
            sub = {"lexical": float(comps["lexical"][row]),
                   "synopsis": float(comps["synopsis"][row]),
                   "keyword": float(comps["keyword"][row])}
            if syn_norm is not None:
                total = syn_w * float(syn_norm.get(tmdb_id, 0.0))
                pos = {k: max(0.0, v) for k, v in sub.items()}
                denom = sum(pos.values()) or 1.0
                for k, v in pos.items():
                    raw[k] = total * v / denom
            else:
                for k, v in sub.items():
                    raw[k] = syn_w * v
        name_w = ctx.get("name_w", 0.0)
        name_scores = ctx.get("name_scores") or {}
        if name_w > 0 and tmdb_id in name_scores:
            raw["name"] = name_w * float(name_scores[tmdb_id])
        return raw

    def _normalize_contributions(self, raw: dict[str, float]) -> list[dict[str, Any]]:
        """Frações (da parte positiva) que somam ~1, da maior para a menor — para
        o usuário ler 'tema 0.6 · sinopse 0.3 · nome 0.1'."""
        positive = {k: max(0.0, v) for k, v in raw.items()}
        total = sum(positive.values())
        items = [
            {"signal": k, "label": SIGNAL_LABELS.get(k, k),
             "share": round(positive[k] / total, 3) if total > 0 else 0.0}
            for k in raw
        ]
        items.sort(key=lambda d: d["share"], reverse=True)
        return items

    def _matched_keywords(self, tmdb_id: int, q_emb: Optional[np.ndarray],
                          topk: int = 4, min_sim: float = 0.30) -> list[str]:
        """Keywords temáticas do filme mais próximas da consulta (multilíngue):
        compara o embedding da consulta com o de cada keyword do filme. É assim
        que 'revivendo o mesmo dia' (PT) acende o chip 'time loop' (EN)."""
        if q_emb is None or self._kw_term_emb is None:
            return []
        names = catalog.get_movie_keywords(tmdb_id)
        pairs = [(nm, self._kw_term_row[nm.lower()]) for nm in names
                 if nm.lower() in self._kw_term_row]
        if not pairs:
            return []
        rows = np.array([r for _nm, r in pairs])
        sims = self._kw_term_emb[rows] @ q_emb
        order = np.argsort(sims)[::-1]
        return [pairs[int(i)][0] for i in order[:topk] if float(sims[i]) >= min_sim]

    def _matched_title_terms(self, query: str, title: Optional[str]) -> list[str]:
        """Tokens (>2 chars) presentes tanto na consulta quanto no título."""
        if not title:
            return []
        qset = {w for w in re.findall(r"\w+", query.lower()) if len(w) > 2}
        out: list[str] = []
        for w in re.findall(r"\w+", title.lower()):
            if len(w) > 2 and w in qset and w not in out:
                out.append(w)
        return out

    def _build_explanation(self, query: str, tmdb_id: int, score: float, ctx: dict,
                           position: int, pool_lo: float, pool_hi: float,
                           constraints: Optional[dict] = None) -> dict[str, Any]:
        """Explicação estruturada de por que o filme ficou nesta posição."""
        exp: dict[str, Any] = {
            "relevance": self._relevance(score, pool_lo, pool_hi),
            "position": position,
            "signals": self._normalize_contributions(self._signal_contributions(tmdb_id, ctx)),
            "matched_keywords": self._matched_keywords(tmdb_id, ctx.get("q_emb")),
            "matched_title_terms": self._matched_title_terms(
                query, self.catalog.get(tmdb_id, {}).get("title")),
        }
        cons = {k: v for k, v in (constraints or {}).items() if v}
        if cons:
            exp["constraints"] = cons
        return exp

    # ================================================================ dispatch
    def search(self, query: str, mode: str = "auto", n: int = 10,
               filters: Optional[dict] = None, role: Optional[str] = None,
               explain: bool = True) -> list[dict[str, Any]]:
        """Busca unificada.

        `mode`: 'name' | 'synopsis' | 'person' | 'keyword' | 'auto'.
        Em 'auto', funde nome (curto) + sinopse (se houver índice).
        `filters`: {year, year_min, year_max, genre, language}.
        `role`: no modo 'person', restringe a 'actor' ou 'director'.
        `explain`: anexa um objeto `explanation` por resultado.
        """
        query = (query or "").strip()
        if not query:
            return []

        ctx: dict[str, Any] = {}
        if mode == "name":
            scored = self.search_by_name(query, n)
            ctx = {"name_scores": dict(scored), "name_w": 1.0, "syn_w": 0.0,
                   "q_emb": self._encode(query) if self._embeddings is not None else None}
        elif mode == "synopsis":
            scored, ctx = self._synopsis_ranked(query, n, blend_name=False)
        elif mode == "person":
            scored = self.search_by_person(query, n, role=role)
        elif mode == "keyword":
            scored = self.search_by_keyword(query, n)
            ctx = {"q_emb": self._encode(query) if self._embeddings is not None else None}
        elif mode == "auto":
            if self.has_synopsis_index:
                scored, ctx = self._synopsis_ranked(query, n, blend_name=True)
            else:
                scored = self.search_by_name(query, n)
                ctx = {"name_scores": dict(scored), "name_w": 1.0, "syn_w": 0.0}
        else:
            raise ValueError(f"modo desconhecido: {mode!r}")

        # Re-rank por sinopse só faz sentido p/ descrição; numa busca de nome
        # (título quase-exato) reordenar pela sinopse atrapalha.
        if mode in ("synopsis", "auto") and self.has_synopsis_index and ctx.get("intent") != "name":
            scored = self._maybe_rerank(query, scored, ctx)

        # Relevância: quando reordenado, escala só pela cabeça reordenada (mesma
        # escala blended); senão, por todo o conjunto.
        rel_scored = scored[:RERANK_POOL] if ctx.get("reranked") else scored
        pool = [s for _tid, s in rel_scored]
        pool_lo, pool_hi = (min(pool), max(pool)) if pool else (0.0, 1.0)

        out: list[dict[str, Any]] = []
        for tmdb_id, score in scored:
            if not self._passes_filters(tmdb_id, filters):
                continue
            item = self._format(tmdb_id, score)
            if explain:
                item["explanation"] = self._build_explanation(
                    query, tmdb_id, score, ctx, len(out) + 1, pool_lo, pool_hi)
            out.append(item)
            if len(out) >= n:
                break
        return out

    def _adaptive_name_weight(self, query: str) -> float:
        """Peso-base do nome conforme o tamanho da consulta: curta parece título
        (nome pesa mais); longa é descrição (a sinopse domina)."""
        n_words = len(query.split())
        return 0.6 if n_words <= 3 else 0.3 if n_words <= 5 else 0.05

    def _best_title_match(self, query: str, titles: list[str]) -> float:
        """Maior similaridade (0–1) da consulta a algum título — para classificar
        INTENÇÃO. Usa `fuzz.ratio` (string inteira), não `WRatio`: o ratio penaliza
        diferença de tamanho, então uma descrição longa NÃO casa com um título
        curto (evita falso 'nome'), mas um título digitado (mesmo com typo) casa."""
        from rapidfuzz import fuzz, process

        if not titles:
            return 0.0
        m = process.extractOne(query, titles, scorer=fuzz.ratio, processor=_name_key)
        return (m[1] / 100.0) if m else 0.0

    def _intent_weight(self, best_title: float, base: float) -> tuple[float, str]:
        """Classifica a INTENÇÃO da consulta pela força do melhor match de título
        e devolve (peso_do_nome, intent). Título (quase) exato ⇒ a consulta É um
        nome → nome domina; senão mantém a base descritiva. Mais confiável que uma
        SLM aqui, porque usa o próprio catálogo (a SLM não conhece os títulos)."""
        if best_title >= 0.92:
            return 0.9, "name"
        if best_title >= 0.85:
            return max(base, 0.6), "name"
        return base, "description"

    def _synopsis_ranked(self, query: str, n: int, blend_name: bool
                         ) -> tuple[list[tuple[int, float]], dict]:
        """Ranqueia por sinopse; em 'auto' (blend_name) funde também o nome.
        Devolve (scored, ctx) — ctx carrega os componentes p/ a explicação."""
        q_emb = self._encode(query) if self._embeddings is not None else None
        comps = self._synopsis_components(query, q_emb=q_emb)
        fused = comps["lexical"] + comps["synopsis"] + comps["keyword"]
        order = np.argsort(fused)[::-1]

        if not blend_name:
            top = order[: n * 4]
            scored = [(int(self._movie_ids[i]), float(fused[i])) for i in top]
            ctx = {"comps": comps, "q_emb": q_emb, "name_scores": {},
                   "name_w": 0.0, "syn_w": 1.0}
            return scored, ctx

        # auto: o sinal de sinopse (z-score, ilimitado) precisa virar [0,1] para
        # ser comparável ao nome (rapidfuzz [0,1]) antes da soma ponderada. O peso
        # do nome é ditado pela INTENÇÃO (título quase-exato ⇒ nome domina).
        name_scores = dict(self.search_by_name(query, n))
        best_title = self._best_title_match(
            query, [self.catalog.get(t, {}).get("title") or "" for t in name_scores])
        name_w, intent = self._intent_weight(best_title, self._adaptive_name_weight(query))
        syn_w = 1.0 - name_w
        row = self._row_index
        cand_ids = {int(self._movie_ids[i]) for i in order[: n * 4]} | set(name_scores)
        syn_raw = {tid: float(fused[row[tid]]) if tid in row else float(fused.min())
                   for tid in cand_ids}
        lo, hi = min(syn_raw.values()), max(syn_raw.values())
        syn_norm = {tid: ((v - lo) / (hi - lo) if hi > lo else 0.0)
                    for tid, v in syn_raw.items()}
        combined = {tid: syn_w * syn_norm[tid] + name_w * name_scores.get(tid, 0.0)
                    for tid in cand_ids}
        scored = sorted(combined.items(), key=lambda kv: kv[1], reverse=True)
        ctx = {"comps": comps, "q_emb": q_emb, "name_scores": name_scores,
               "name_w": name_w, "syn_w": syn_w, "syn_norm": syn_norm, "intent": intent}
        return scored, ctx

    # ============================================================== combinada
    @property
    def _row_index(self) -> dict[int, int]:
        if self._row_index_cache is None:
            self._row_index_cache = (
                {int(t): i for i, t in enumerate(self._movie_ids)}
                if self._movie_ids is not None else {}
            )
        return self._row_index_cache

    def _movies_by_person_name(self, name: str, role: Optional[str]) -> set[int]:
        """tmdb_ids dos filmes de uma pessoa (nome exato), opcionalmente por papel."""
        sql = ("SELECT mp.tmdb_id AS tmdb_id FROM people p "
               "JOIN movie_people mp ON mp.person_id = p.person_id WHERE p.name = ?")
        params: list[Any] = [name]
        if role in ("actor", "director"):
            sql += " AND mp.role = ?"
            params.append(role)
        return {r["tmdb_id"] for r in db.query(sql, params)}

    def _rank_candidates(self, query: str, cand_ids: list[int]) -> list[tuple[int, float]]:
        return self._rank_candidates_ctx(query, cand_ids)[0]

    def _rank_candidates_ctx(self, query: str, cand_ids: list[int]
                             ) -> tuple[list[tuple[int, float]], dict]:
        """Ranqueia um conjunto restrito (filmes de um diretor/ator) por consulta
        livre, reaproveitando os mesmos sinais z-score da busca por sinopse + o
        nome. Como a pessoa já restringiu o conjunto, o texto quase sempre é uma
        descrição de enredo — então a sinopse pesa mais que na busca global.
        Devolve (scored, ctx) para a explicação."""
        from rapidfuzz import fuzz

        q_emb = self._encode(query) if self._embeddings is not None else None
        comps = self._synopsis_components(query, q_emb=q_emb) if self.has_synopsis_index else None
        row = self._row_index

        qk = _name_key(query)
        name_scores = {tid: _name_score(qk, self.catalog.get(tid, {}).get("title") or "")
                       for tid in cand_ids}
        # Intenção: num conjunto já restrito o texto costuma DESCREVER o enredo
        # (base 0.2, nome só desempata); mas se a consulta casa (quase) exato com
        # o título de um candidato, ela É um nome → o nome domina.
        best_title = max(name_scores.values(), default=0.0)
        name_w, intent = self._intent_weight(best_title, 0.2)
        syn_w = 1.0 - name_w
        # Sinopse z-score -> [0,1] dentro do conjunto restrito (comparável ao nome).
        syn_norm: dict[int, float] = {}
        if comps is not None:
            syn_raw = {tid: float(comps["lexical"][row[tid]] + comps["synopsis"][row[tid]]
                                  + comps["keyword"][row[tid]]) if tid in row else 0.0
                       for tid in cand_ids}
            lo, hi = min(syn_raw.values()), max(syn_raw.values())
            syn_norm = {tid: ((v - lo) / (hi - lo) if hi > lo else 0.0)
                        for tid, v in syn_raw.items()}
        combined = {tid: name_w * name_scores[tid] + syn_w * syn_norm.get(tid, 0.0)
                    for tid in cand_ids}
        scored = sorted(combined.items(), key=lambda kv: kv[1], reverse=True)
        ctx = {"comps": comps, "q_emb": q_emb, "name_scores": name_scores,
               "name_w": name_w, "syn_w": syn_w, "syn_norm": syn_norm, "intent": intent}
        return scored, ctx

    def search_combined(self, query: Optional[str] = None, director: Optional[str] = None,
                        actor: Optional[str] = None, n: int = 10,
                        filters: Optional[dict] = None) -> list[dict[str, Any]]:
        """Busca facetada: diretor/ator **restringem** (o filme precisa tê-los) e
        a consulta livre (sinopse/nome) **ranqueia** dentro do conjunto. Sem
        consulta, ordena por popularidade. Sem diretor/ator, cai na busca normal.
        """
        query = (query or "").strip()
        director = (director or "").strip()
        actor = (actor or "").strip()

        # Sem restrição de pessoa: busca de texto normal (auto).
        if not director and not actor:
            return self.search(query, mode="auto", n=n, filters=filters) if query else []

        # Interseção das restrições de pessoa.
        constraint: Optional[set[int]] = None
        for name, role in ((director, "director"), (actor, "actor")):
            if name:
                ids = self._movies_by_person_name(name, role)
                constraint = ids if constraint is None else (constraint & ids)

        cands = [tid for tid in (constraint or set()) if self._passes_filters(tid, filters)]
        if not cands:
            return []

        constraints = {"director": director or None, "actor": actor or None}
        if query:
            scored, ctx = self._rank_candidates_ctx(query, cands)
            # Re-rank por sinopse só para descrição; se o texto é um título exato
            # (intent=name), o nome já manda e reordenar pela sinopse atrapalha.
            if ctx.get("intent") != "name":
                scored = self._maybe_rerank(query, scored, ctx, min_words=1)
        else:
            # Sem texto: ordena por popularidade (a pessoa é a única restrição).
            scored = sorted(
                ((tid, float(self.catalog.get(tid, {}).get("popularity") or 0.0)) for tid in cands),
                key=lambda kv: kv[1], reverse=True,
            )
            ctx = {"q_emb": None}

        rel_scored = scored[:RERANK_POOL] if ctx.get("reranked") else scored
        pool = [s for _tid, s in rel_scored]
        pool_lo, pool_hi = (min(pool), max(pool)) if pool else (0.0, 1.0)
        out: list[dict[str, Any]] = []
        for tid, s in scored[:n]:
            item = self._format(tid, s)
            item["explanation"] = self._build_explanation(
                query, tid, s, ctx, len(out) + 1, pool_lo, pool_hi, constraints=constraints)
            out.append(item)
        return out


def suggest_people(prefix: str, role: Optional[str] = None, limit: int = 10
                   ) -> list[dict[str, Any]]:
    """Autocomplete de pessoas: nomes que contêm `prefix`, ordenados por nº de
    créditos (mais prolíficos primeiro). `role` opcional ('actor'|'director').
    Devolve [{name, credits, roles}]."""
    prefix = (prefix or "").strip()
    if len(prefix) < 2:
        return []
    sql = """
        SELECT p.name AS name, COUNT(*) AS credits,
               GROUP_CONCAT(DISTINCT mp.role) AS roles
        FROM people p JOIN movie_people mp ON mp.person_id = p.person_id
        WHERE p.name LIKE ?
    """
    params: list[Any] = [f"%{prefix}%"]
    if role in ("actor", "director"):
        sql += " AND mp.role = ?"
        params.append(role)
    sql += " GROUP BY p.person_id ORDER BY credits DESC LIMIT ?"
    params.append(limit)
    return db.query(sql, params)


# Singleton preguiçoso para reuso entre requisições.
_engine: Optional[SearchEngine] = None


def get_engine() -> SearchEngine:
    global _engine
    if _engine is None:
        _engine = SearchEngine()
    return _engine

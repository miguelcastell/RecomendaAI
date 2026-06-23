"""ConstrÃ³i e serializa os Ã­ndices de busca por sinopse dos 22k filmes.

Gera, em `retrieval/index/`:
  - `movie_ids.npy`         ordem das linhas (tmdb_id) â€” compartilhada por todos os Ã­ndices
  - `bm25_vectorizer.pkl`   CountVectorizer (stopwords PT) ajustado nas sinopses
  - `bm25_counts.npz`       matriz de contagens esparsa (sinal lexical BM25)
  - `embeddings.npy`        embeddings multilÃ­ngues L2-normalizados (float32, NÃ—384)
  - `kw_embeddings.npy`     embeddings temÃ¡ticos (gÃªneros+keywords) L2-normalizados
  - `meta.json`             metadados (modelo, dim, contagens, parÃ¢metros)

A lÃ³gica fica aqui (testÃ¡vel via CLI/notebook); o notebook
`research/build_search_index.ipynb` apenas chama `build_index()` e reporta.
"""

from __future__ import annotations

import json
import os
import pickle
import time
from typing import Optional

import numpy as np

from core import catalog, db

INDEX_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index")

MOVIE_IDS_PATH = os.path.join(INDEX_DIR, "movie_ids.npy")
BM25_VECTORIZER_PATH = os.path.join(INDEX_DIR, "bm25_vectorizer.pkl")
BM25_COUNTS_PATH = os.path.join(INDEX_DIR, "bm25_counts.npz")
EMBEDDINGS_PATH = os.path.join(INDEX_DIR, "embeddings.npy")
KW_EMBEDDINGS_PATH = os.path.join(INDEX_DIR, "kw_embeddings.npy")
KEYWORD_TERM_EMB_PATH = os.path.join(INDEX_DIR, "keyword_term_embeddings.npy")
KEYWORD_TERMS_PATH = os.path.join(INDEX_DIR, "keyword_terms.json")
META_PATH = os.path.join(INDEX_DIR, "meta.json")

# Artefatos do Ã­ndice TF-IDF antigo (removidos no rebuild â€” agora usamos BM25).
_LEGACY_PATHS = [
    os.path.join(INDEX_DIR, "tfidf_vectorizer.pkl"),
    os.path.join(INDEX_DIR, "tfidf_matrix.npz"),
]

DEFAULT_EMBED_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

# Fallback caso o corpus do NLTK nÃ£o esteja disponÃ­vel (mantÃ©m o sistema
# funcionando offline). Lista enxuta de stopwords PT.
_PT_STOPWORDS_FALLBACK = [
    "a", "Ã ", "ao", "aos", "as", "Ã s", "com", "como", "da", "das", "de", "do",
    "dos", "e", "Ã©", "em", "entre", "essa", "esse", "esta", "este", "eu", "foi",
    "isso", "mais", "mas", "me", "mesmo", "na", "nas", "no", "nos", "nÃ£o", "o",
    "os", "ou", "para", "pela", "pelo", "por", "que", "se", "sem", "ser", "seu",
    "sua", "sÃ£o", "tambÃ©m", "te", "tem", "um", "uma", "vocÃª", "Ã ",
]


def portuguese_stopwords() -> list[str]:
    """Stopwords PT do NLTK (como no notebook legado); fallback baked-in."""
    try:
        from nltk.corpus import stopwords

        try:
            return stopwords.words("portuguese")
        except LookupError:
            import nltk

            nltk.download("stopwords", quiet=True)
            return stopwords.words("portuguese")
    except Exception:
        return list(_PT_STOPWORDS_FALLBACK)


def _build_keyword_documents(ids: np.ndarray) -> list[str]:
    """Documento temÃ¡tico por filme: gÃªneros + keywords da TMDB.

    As keywords ("time loop", "memory loss", "viagem no tempo") sÃ£o o gancho que
    casa com descriÃ§Ãµes de enredo. Vira um **embedding separado** (nÃ£o Ã© misturado
    Ã  sinopse, pra nÃ£o diluir o embedding principal nem injetar o ruÃ­do de keywords
    irrelevantes â€” "alarm clock", "telecaster" â€” no texto da sinopse)."""
    gmap = catalog.genres_by_movie()
    kmap = catalog.keywords_by_movie()
    return [" ".join(gmap.get(int(t), []) + kmap.get(int(t), [])) for t in ids.tolist()]


def build_index(
    embed_model_name: str = DEFAULT_EMBED_MODEL,
    with_embeddings: bool = True,
    limit: Optional[int] = None,
    batch_size: int = 64,
    show_progress: bool = True,
) -> dict:
    """ConstrÃ³i os Ã­ndices e salva em `retrieval/index/`.

    Gera, com `with_embeddings`, **dois** espaÃ§os de embedding: o da sinopse
    (`embeddings.npy`) e o temÃ¡tico de keywords/gÃªneros (`kw_embeddings.npy`),
    combinados na busca. O sinal lexical (BM25) Ã© sÃ³ da sinopse.
    `limit` restringe aos N primeiros filmes; `with_embeddings=False` gera sÃ³ BM25.
    """
    from retrieval.bm25 import BM25Index

    os.makedirs(INDEX_DIR, exist_ok=True)

    df = catalog.get_catalog_df()
    if limit is not None:
        df = df.head(limit)

    ids = df["tmdb_id"].to_numpy(dtype=np.int64)
    docs = df["overview"].fillna("").tolist()  # sinopse pura: base do BM25 e do embedding principal
    n = len(docs)

    # --- BM25 lexical (CountVectorizer com stopwords PT) ---
    t0 = time.time()
    stop = portuguese_stopwords()
    bm25 = BM25Index.build(docs, stop_words=stop)
    bm25_secs = round(time.time() - t0, 1)

    np.save(MOVIE_IDS_PATH, ids)
    bm25.save(BM25_VECTORIZER_PATH, BM25_COUNTS_PATH)
    for legacy in _LEGACY_PATHS:  # limpa o Ã­ndice TF-IDF antigo, se existir
        if os.path.exists(legacy):
            os.remove(legacy)

    meta = {
        "n_movies": int(n),
        "lexical": "bm25",
        "bm25_vocab_size": int(bm25.vocab_size),
        "bm25_k1": bm25.k1,
        "bm25_b": bm25.b,
        "bm25_build_secs": bm25_secs,
        "has_embeddings": False,
        "has_keyword_embeddings": False,
        "has_keyword_terms": False,
        "embed_model": None,
        "embed_dim": None,
        "built_at": int(time.time()),
    }

    # --- Embeddings multilÃ­ngues (L2-normalizados): sinopse + temÃ¡tico ---
    if with_embeddings:
        from sentence_transformers import SentenceTransformer

        t0 = time.time()
        model = SentenceTransformer(embed_model_name)

        emb = model.encode(
            docs, batch_size=batch_size, normalize_embeddings=True,
            show_progress_bar=show_progress, convert_to_numpy=True,
        ).astype(np.float32)
        np.save(EMBEDDINGS_PATH, emb)

        kw_docs = _build_keyword_documents(ids)
        kw_emb = model.encode(
            kw_docs, batch_size=batch_size, normalize_embeddings=True,
            show_progress_bar=show_progress, convert_to_numpy=True,
        ).astype(np.float32)
        np.save(KW_EMBEDDINGS_PATH, kw_emb)

        # Embedding por keyword distinta (nÃ£o por filme): permite, na explicaÃ§Ã£o,
        # dizer QUAIS keywords temÃ¡ticas casaram com a consulta â€” de forma
        # multilÃ­ngue (a consulta em PT casa "time loop"/"viagem no tempo").
        kw_rows = db.query("SELECT keyword_id, name FROM keywords ORDER BY keyword_id")
        kw_names = [r["name"] for r in kw_rows]
        kw_term_emb = model.encode(
            kw_names, batch_size=batch_size, normalize_embeddings=True,
            show_progress_bar=show_progress, convert_to_numpy=True,
        ).astype(np.float32)
        np.save(KEYWORD_TERM_EMB_PATH, kw_term_emb)
        with open(KEYWORD_TERMS_PATH, "w", encoding="utf-8") as f:
            json.dump(kw_names, f, ensure_ascii=False)

        meta.update(
            has_embeddings=True,
            has_keyword_embeddings=True,
            has_keyword_terms=True,
            n_keyword_terms=len(kw_names),
            embed_model=embed_model_name,
            embed_dim=int(emb.shape[1]),
            embed_build_secs=round(time.time() - t0, 1),
        )
    else:
        # Remove embeddings antigos para nÃ£o dessincronizar com movie_ids.
        for path in (EMBEDDINGS_PATH, KW_EMBEDDINGS_PATH,
                     KEYWORD_TERM_EMB_PATH, KEYWORD_TERMS_PATH):
            if os.path.exists(path):
                os.remove(path)

    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    return meta


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="ConstrÃ³i o Ã­ndice de busca por sinopse.")
    p.add_argument("--no-embeddings", action="store_true", help="SÃ³ TF-IDF.")
    p.add_argument("--limit", type=int, default=None, help="Limitar a N filmes.")
    p.add_argument("--model", default=DEFAULT_EMBED_MODEL)
    p.add_argument("--batch-size", type=int, default=64)
    args = p.parse_args()

    info = build_index(
        embed_model_name=args.model,
        with_embeddings=not args.no_embeddings,
        limit=args.limit,
        batch_size=args.batch_size,
    )
    print(json.dumps(info, ensure_ascii=False, indent=2))

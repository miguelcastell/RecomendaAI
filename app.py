"""RecomendAI — API Flask.

Três rotas principais:
  - POST /search       → busca textual (sinopse + nome + filtros) — motor superior
  - POST /submit_ratings → recomendar baseado em 3 filmes favoritos
  - POST /recommend    → recomendação via upload ratings.csv do Letterboxd

Os modelos (índice de busca / fatores do recomendador) são carregados sob
demanda (singletons) no primeiro uso de cada rota.
"""

from __future__ import annotations

import os

from flask import Flask, jsonify, render_template, request

from core import catalog, posters

app = Flask(__name__, static_folder="frontend", template_folder="frontend")


# =========================================================================
# ROTA PRINCIPAL
# =========================================================================

@app.route("/")
def home_page():
    return render_template("index.html")


# =========================================================================
# ROTAS DE BUSCA (motor superior — davidogral)
# =========================================================================

@app.route("/genres")
def genres():
    """Lista de gêneros (para o filtro da busca)."""
    names = sorted(catalog.get_genre_names().values())
    return jsonify(names)


@app.route("/search", methods=["POST"])
def search():
    """Busca facetada. Body JSON: {query, director, actor, n, year_min,
    year_max, genre, language}. Diretor/ator restringem; query ranqueia."""
    data = request.get_json(silent=True) or {}
    query = (data.get("query") or "").strip()
    director = (data.get("director") or "").strip()
    actor = (data.get("actor") or "").strip()
    if not query and not director and not actor:
        return jsonify({"error": "Informe um termo, um diretor ou um ator."}), 400

    try:
        n = max(1, min(int(data.get("n", 12)), 50))
    except (TypeError, ValueError):
        n = 12

    filters = {}
    for key in ("year_min", "year_max"):
        val = data.get(key)
        if val not in (None, ""):
            try:
                filters[key] = int(val)
            except (TypeError, ValueError):
                pass
    if data.get("genre"):
        filters["genre"] = data["genre"]
    if data.get("language"):
        filters["language"] = data["language"]

    try:
        from retrieval.search_engine import get_engine

        results = get_engine().search_combined(
            query=query, director=director, actor=actor, n=n, filters=filters or None)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 503
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({
        "query": query,
        "director": director,
        "actor": actor,
        "count": len(results),
        "results": posters.attach(results),
    })


@app.route("/people")
def people():
    """Autocomplete de diretor/ator. Query params: q, role (actor|director)."""
    q = request.args.get("q", "")
    role = request.args.get("role") if request.args.get("role") in ("actor", "director") else None
    from retrieval.search_engine import suggest_people

    return jsonify(suggest_people(q, role=role, limit=10))


# =========================================================================
# ROTA: CATÁLOGO (para autocomplete de filmes — compatibilidade)
# =========================================================================

@app.route("/get_movies")
def get_movies():
    """Retorna todos os filmes do catálogo para autocomplete no frontend."""
    try:
        cat = catalog.get_catalog()
        from core.catalog import get_movie_genres
        movie_list = [
            {
                "movie_id": tid,
                "title": mv.get("title", ""),
                "poster_path": "",
                "genres": get_movie_genres(tid),
            }
            for tid, mv in cat.items()
        ]
        movie_list.sort(key=lambda x: x["title"])
        return jsonify(movie_list)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/popular")
def popular():
    """Filmes mais famosos (por nº de votos) para a seleção visual — com pôster.

    Fama ≈ vote_count (quantas pessoas avaliaram); filtramos por vote_average>=6.5
    para não trazer famoso-porém-ruim. Paginação simples via `offset`."""
    try:
        n = max(1, min(int(request.args.get("n", 48)), 120))
        offset = max(0, int(request.args.get("offset", 0)))
    except (TypeError, ValueError):
        n, offset = 48, 0
    cat = catalog.get_catalog()
    ranked = sorted(
        (m for m in cat.values() if (m.get("vote_average") or 0) >= 6.5),
        key=lambda m: (m.get("vote_count") or 0), reverse=True,
    )[offset:offset + n]
    items = [{"tmdb_id": m["tmdb_id"], "title": m.get("title"),
              "release_year": m.get("release_year")} for m in ranked]
    return jsonify(posters.attach(items))


# =========================================================================
# ROTA: SUBMIT RATINGS (3 filmes favoritos — do projeto original)
# =========================================================================

@app.route("/submit_ratings", methods=["POST"])
def submit_ratings():
    """Recomenda a partir de filmes favoritos selecionados (qualquer quantidade).

    Aceita JSON {movie_ids: [...]} ou form (movie_ids repetido / movie_id_1..N).
    Usa o fluxo de perfil (vetor de gosto por conteúdo + colaborativo) e devolve
    também o perfil traçado."""
    try:
        ids: list[int] = []
        data = request.get_json(silent=True) or {}
        raw = data.get("movie_ids") if isinstance(data.get("movie_ids"), list) else None
        if raw is None:
            raw = request.form.getlist("movie_ids") or [
                request.form.get(f"movie_id_{i}") for i in range(1, 11)
            ]
        for x in raw:
            try:
                if x is not None and int(x) > 0:
                    ids.append(int(x))
            except (TypeError, ValueError):
                continue
        ids = list(dict.fromkeys(ids))  # dedup preservando ordem
        if not ids:
            return jsonify({"error": "Selecione ao menos um filme."}), 400

        from recommender.profile import recommend_from_profile

        detail = [{"tmdb_id": mid, "rating": 5.0, "name": None, "year": None, "review": ""}
                  for mid in ids]
        result = recommend_from_profile(detail, n=15)
        return jsonify({
            "message": "Recomendações personalizadas geradas!",
            "profile": result["profile"],
            "recommendations": posters.attach(result["recommendations"]),
        })

    except RuntimeError as e:
        return jsonify({
            "error": str(e),
            "message": "Modelo de recomendação não encontrado. Use a busca para encontrar filmes!",
            "recommendations": [],
        }), 503
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =========================================================================
# ROTA: RECOMMEND (via Letterboxd ratings.csv — davidogral)
# =========================================================================

@app.route("/recommend", methods=["POST"])
def recommend():
    """Recomendação via upload ratings.csv do Letterboxd."""
    file = request.files.get("ratings")
    if file is None or not file.filename:
        return jsonify({"error": "Envie o arquivo ratings.csv do Letterboxd."}), 400
    try:
        n = max(1, min(int(request.form.get("n", 20)), 50))
    except (TypeError, ValueError):
        n = 20

    try:
        from recommender.letterboxd import import_ratings
        from recommender.profile import recommend_from_profile

        imported = import_ratings(file, resolver="auto")
        if not imported.matched:
            return jsonify({
                "error": "Nenhum filme do seu ratings.csv foi encontrado no catálogo.",
                "total_rows": imported.total_rows,
                "matched": 0,
            }), 422
        # Perfil de gosto: vetor de conteúdo (embeddings) + resumo + colaborativo.
        result = recommend_from_profile(imported.matched_detail, n=n)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 503

    return jsonify({
        "total_rows": imported.total_rows,
        "matched": len(imported.matched),
        "match_rate": round(imported.match_rate, 3),
        "unmatched_count": len(imported.unmatched),
        "method": "perfil (conteúdo + colaborativo)",
        "profile": result["profile"],
        "recommendations": posters.attach(result["recommendations"]),
    })


# =========================================================================
# HEALTH CHECK
# =========================================================================

@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(debug=True, host="0.0.0.0", port=port)

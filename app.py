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


def _with_poster(item: dict) -> dict:
    item = dict(item)
    tid = item.get("tmdb_id") or item.get("movie_id")
    if tid:
        item["poster"] = posters.get_poster(int(tid), item.get("title"))
    else:
        item["poster"] = posters.get_poster(0, item.get("title"))
    return item


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
        "results": [_with_poster(r) for r in results],
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


# =========================================================================
# ROTA: SUBMIT RATINGS (3 filmes favoritos — do projeto original)
# =========================================================================

@app.route("/submit_ratings", methods=["POST"])
def submit_ratings():
    """Recomenda filmes baseado em 3 filmes favoritos selecionados pelo usuário."""
    try:
        movie_ids_raw = []
        for i in range(1, 4):
            mid = request.form.get(f"movie_id_{i}")
            if mid and mid.isdigit():
                movie_ids_raw.append(int(mid))

        if not movie_ids_raw:
            return jsonify({"error": "Nenhum filme selecionado"}), 400

        # Usar o CollaborativeRecommender no modo item-item
        from recommender.collaborative import get_recommender

        user_ratings = [(mid, 5.0) for mid in movie_ids_raw]
        recs = get_recommender().recommend(user_ratings, n=15)

        return jsonify({
            "message": "Recomendações personalizadas geradas!",
            "recommendations": [_with_poster(r) for r in recs],
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
        from recommender.collaborative import get_recommender

        imported = import_ratings(file, resolver="fuzzy")
        if not imported.matched:
            return jsonify({
                "error": "Nenhum filme do seu ratings.csv foi encontrado no catálogo.",
                "total_rows": imported.total_rows,
                "matched": 0,
            }), 422
        recs = get_recommender().recommend(imported.matched, n=n)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 503

    return jsonify({
        "total_rows": imported.total_rows,
        "matched": len(imported.matched),
        "match_rate": round(imported.match_rate, 3),
        "unmatched_count": len(imported.unmatched),
        "method": recs[0]["method"] if recs else None,
        "recommendations": [_with_poster(r) for r in recs],
    })


# =========================================================================
# HEALTH CHECK
# =========================================================================

@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)

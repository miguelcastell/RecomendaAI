from flask import Flask, jsonify, request, render_template
from models.recommendation import MovieRecommender
from database.models import init_db, SessionLocal, UserRating
import os

# Inicializar Banco de Dados
init_db()

app = Flask(__name__, static_folder='frontend', template_folder='frontend')

# Inicializar Recomendor
recommender = MovieRecommender("data/tmdb_movies_large.json")

@app.route("/")
def home_page():
    return render_template("index.html")

@app.route("/get_movies")
def get_movies():
    try:
        movie_list = [
            {
                "movie_id": movie["id"],
                "title": movie["title"],
                "poster_path": movie.get("poster_path", ""),
                "genres": movie.get("genres", [])
            }
            for movie in recommender.movies
        ]
        movie_list.sort(key=lambda x: x["title"])
        return jsonify(movie_list)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/submit_ratings", methods=["POST"])
def submit_ratings():
    session = SessionLocal()
    try:
        user_id_raw = request.form.get("user_id")
        if not user_id_raw or not user_id_raw.isdigit():
            return jsonify({"error": "user_id inválido"}), 400

        user_id = int(user_id_raw)
        movie_ids = []
        for i in range(1, 4):
            movie_id_raw = request.form.get(f"movie_id_{i}")
            if movie_id_raw and movie_id_raw.isdigit():
                movie_ids.append(int(movie_id_raw))

        if not movie_ids:
            return jsonify({"error": "Nenhum filme selecionado"}), 400

        # Salvar no banco de dados para treinamento futuro
        for m_id in movie_ids:
            new_rating = UserRating(
                user_id=user_id,
                movie_id=m_id,
                rating=5.0, # Assumindo 5 estrelas para filmes selecionados
                movie_title=next((m['title'] for m in recommender.movies if m['id'] == m_id), "Desconhecido")
            )
            session.add(new_rating)
        session.commit()

        # Gerar recomendações usando o sistema híbrido
        recommendations = recommender.recommend_for_user(
            user_id,
            n=15,
            selected_movie_ids=movie_ids
        )

        return jsonify({
            "message": "✅ Recomendações personalizadas geradas!",
            "user_id": user_id,
            "recommendations": recommendations
        })

    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)

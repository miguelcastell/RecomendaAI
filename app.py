from flask import Flask, jsonify, request, render_template
from models.recommendation import MovieRecommender

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

app = Flask(__name__, static_folder='frontend', template_folder='frontend')

print("🔍 Inicializando MovieRecommender...")
recommender = MovieRecommender("data/tmdb_movies_large.json")

if hasattr(recommender, 'movies'):
    print(f"✅ MovieRecommender carregado com {len(recommender.movies)} filmes!")
    for i, movie in enumerate(recommender.movies[:3]):
        print(f"   🎬 {i+1}. {movie.get('title', 'Sem título')} - Gêneros: {movie.get('genres', [])}")
else:
    print("❌ MovieRecommender não carregou filmes!")

@app.route("/")
def home_page():
    return render_template("index.html")

@app.route("/get_movies")
def get_movies():
    try:
        if not hasattr(recommender, 'movies') or not recommender.movies:
            return jsonify({"error": "Dataset de filmes não carregado"}), 500
        
        movie_list = [
            {"movie_id": movie["id"], "title": movie["title"]}
            for movie in recommender.movies
        ]
        
        movie_list.sort(key=lambda x: x["title"])
        return jsonify(movie_list)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/submit_ratings", methods=["POST"])
def submit_ratings():
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

        recommendations = recommender.recommend_for_user(
            user_id,
            n=15,
            selected_movie_ids=movie_ids
        )

        rec_with_details = []
        for item in recommendations:
            if len(item) == 4:
                movie_id, rating, title, poster = item
            else:
                movie_id, rating = item
                title = f"Filme {movie_id}"
                poster = "https://placehold.co/200x300/141414/FFFFFF?font=roboto&text=Sem+Poster"

            rec_with_details.append({
                "movie_id": int(movie_id),
                "title": title,
                "poster": poster,
                "predicted_rating": float(rating)
            })

        return jsonify({
            "message": "✅ Recomendações por gênero geradas!",
            "user_id": user_id,
            "recommendations": rec_with_details
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
# app.py — Sistema de Recomendação de Filmes — VERSÃO TMDB + FRONTEND MODERNO
from flask import Flask, jsonify, request, render_template, send_from_directory
from models.recommendation import MovieRecommender
from utils.movie_loader import load_movie_names, load_movies_data
from utils.movie_poster import get_movie_poster
import os
import time

app = Flask(__name__, static_folder='frontend', template_folder='frontend')

# Inicializa o recomendador com dataset TMDB
try:
    recommender = MovieRecommender("data/tmdb_movies.json")
    print(f"✅ Modelo carregado com {len(recommender.movies)} filmes do TMDB!")
except Exception as e:
    print(f"❌ Erro ao carregar o modelo: {e}")
    recommender = None

# ================
# ROTAS FRONT-END
# ================

@app.route("/")
def home_page():
    """Redireciona para o frontend estilo Lovable"""
    return render_template("index.html")

# ================
# ROTAS API (BACK-END)
# ================

@app.route("/get_movies")
def get_movies():
    """Retorna lista de filmes para o frontend"""
    try:
        movies_data = load_movies_data()
        movie_list = []
        
        for movie in movies_data:
            movie_list.append({
                "movie_id": movie['id'],
                "title": movie['title']
            })
        
        # Ordena por título
        movie_list.sort(key=lambda x: x["title"])
        return jsonify(movie_list)
        
    except Exception as e:
        print(f"❌ Erro em /get_movies: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/submit_ratings", methods=["POST"])
def submit_ratings():
    """Recebe avaliações e retorna recomendações personalizadas"""
    try:
        user_id = int(request.form.get("user_id"))
        print(f"👤 Usuário: {user_id}")
        
        # Pega os filmes selecionados
        movie_ids = []
        for i in range(1, 4):
            movie_id = request.form.get(f"movie_id_{i}")
            if movie_id:
                movie_ids.append(int(movie_id))
        
        print(f"🎬 Filmes selecionados: {movie_ids}")
        
        if not movie_ids:
            return jsonify({"error": "Nenhum filme selecionado"}), 400

        # Gera recomendações
        global recommender
        if recommender is None:
            recommender = MovieRecommender("data/tmdb_movies.json")
        
        recommendations = recommender.recommend_for_user(user_id, n=15)
        print(f"✅ Gerou {len(recommendations)} recomendações")
        
        # Adiciona detalhes
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
            "message": "✅ Avaliações processadas e recomendações geradas!",
            "user_id": user_id,
            "recommendations": rec_with_details
        })

    except Exception as e:
        print(f"❌ Erro em /submit_ratings: {e}")
        return jsonify({"error": str(e)}), 500

# ================
# SERVIR ARQUIVOS ESTÁTICOS
# ================

@app.route('/frontend/<path:filename>')
def serve_frontend(filename):
    return send_from_directory('frontend', filename)

# ================
# RODAR APLICAÇÃO
# ================ 

@app.route('/assets/<path:filename>')
def serve_assets(favicon):
    return send_from_directory('assets', favicon)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
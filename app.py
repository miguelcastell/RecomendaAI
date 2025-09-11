# app.py — Sistema de Recomendação de Filmes — VERSÃO FINAL COM DEBUG
from flask import Flask, jsonify, request, render_template
import os
import json

# ✅ IMPORTANTE: Importa o MovieRecommender
from models.recommendation import MovieRecommender

# ✅ Carrega variáveis de ambiente (pra desenvolvimento local)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

app = Flask(__name__, static_folder='frontend', template_folder='frontend')

# ✅ Inicializa o recomendador com o dataset grande
print("🔍 Inicializando MovieRecommender...")
recommender = MovieRecommender("data/tmdb_movies_large.json")

# ✅ DEBUG: Verifica quantos filmes foram carregados
if hasattr(recommender, 'movies'):
    print(f"✅ MovieRecommender carregado com {len(recommender.movies)} filmes!")
    # Mostra 3 primeiros filmes
    for i, movie in enumerate(recommender.movies[:3]):
        print(f"   🎬 {i+1}. {movie.get('title', 'Sem título')} - Gêneros: {movie.get('genres', [])}")
else:
    print("❌ MovieRecommender não carregou filmes!")

# ================
# ROTAS FRONT-END
# ================

@app.route("/")
def home_page():
    """Redireciona para o frontend"""
    return render_template("index.html")

# ================
# ROTAS API (BACK-END)
# ================

@app.route("/get_movies")
def get_movies():
    """Retorna lista de filmes para o frontend"""
    try:
        if not hasattr(recommender, 'movies') or not recommender.movies:
            return jsonify({"error": "Dataset de filmes não carregado"}), 500
        
        movie_list = []
        for movie in recommender.movies:
            movie_list.append({
                "movie_id": movie['id'],
                "title": movie['title']
            })
        
        print(f"📋 Enviando {len(movie_list)} filmes para o frontend")
        movie_list.sort(key=lambda x: x["title"])
        return jsonify(movie_list)
        
    except Exception as e:
        print(f"❌ Erro em /get_movies: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/submit_ratings", methods=["POST"])
def submit_ratings():
    """Recebe avaliações e retorna recomendações personalizadas por gênero"""
    try:
        user_id = int(request.form.get("user_id"))
        print(f"\n👤 Usuário: {user_id}")
        
        # Pega os filmes selecionados
        movie_ids = []
        for i in range(1, 4):
            movie_id = request.form.get(f"movie_id_{i}")
            if movie_id:
                movie_ids.append(int(movie_id))
        
        print(f"🎬 Filmes selecionados: {movie_ids}")
        
        if not movie_ids:
            return jsonify({"error": "Nenhum filme selecionado"}), 400

        # ✅ DEBUG: Verifica se os filmes existem no dataset
        selected_titles = []
        for movie_id in movie_ids:
            for movie in recommender.movies:
                if movie['id'] == movie_id:
                    selected_titles.append(movie['title'])
                    break
        print(f"✅ Filmes encontrados: {selected_titles}")

        # Gera recomendações BASEADO NOS GÊNEROS
        print("🧠 Gerando recomendações por gênero...")
        recommendations = recommender.recommend_for_user(user_id, n=15, selected_movie_ids=movie_ids)
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
            print(f"   🍿 Recomendado: {title} (Nota: {rating:.1f})")

        return jsonify({
            "message": "✅ Recomendações por gênero geradas!",
            "user_id": user_id,
            "recommendations": rec_with_details
        })

    except Exception as e:
        print(f"❌ Erro em /submit_ratings: {e}")
        return jsonify({"error": str(e)}), 500

# ================
# RODAR APLICAÇÃO
# ================

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000) 
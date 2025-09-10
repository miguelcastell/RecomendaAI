# app.py
from flask import Flask, jsonify
from models.recommendation import MovieRecommender
import os

app = Flask(__name__)

# Caminho do dataset
DATA_PATH = os.path.join("data", "ratings.csv")

# Inicializa o recomendador
try:
    recommender = MovieRecommender(DATA_PATH)
    print("✅ Modelo carregado e treinado com sucesso!")
except Exception as e:
    print(f"❌ Erro ao carregar o modelo: {e}")
    recommender = None

@app.route("/")
def home():
    return jsonify({
        "message": "🎬 Bem-vindo ao RecomendaAí!",
        "status": "online" if recommender else "offline",
        "endpoints": {
            "GET /recommend/<int:user_id>": "Recomenda 5 filmes para o usuário"
        }
    })

@app.route("/recommend/<int:user_id>")
def recommend(user_id):
    if not recommender:
        return jsonify({"error": "Modelo não carregado."}), 500

    try:
        recommendations = recommender.recommend_for_user(user_id, n=5)
        return jsonify({
            "user_id": user_id,
            "recommendations": [
                {"movie_id": int(movie_id), "predicted_rating": float(rating)}
                for movie_id, rating in recommendations
            ]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
    
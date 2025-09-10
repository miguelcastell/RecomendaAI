# app.py — Sistema de Recomendação de Filmes — VERSÃO COMPLETA + FRONTEND LOVABLE
from flask import Flask, jsonify, request, render_template, send_from_directory
from models.recommendation import MovieRecommender
from utils.movie_loader import load_movie_names
from utils.movie_poster import get_movie_poster
import os
import pandas as pd
import time

def translate_movie_title(title):
    """Traduz títulos de filmes para português (versão simplificada)"""
    translations = {
        "Toy Story": "Toy Story: Um Mundo de Aventuras",
        "Star Wars": "Guerra nas Estrelas",
        "Contact": "Contato",
        "Fargo": "Fargo: Uma Comédia de Erros",
        "Star Trek": "Jornada nas Estrelas",
        "The Matrix": "Matrix",
        "The Godfather": "O Poderoso Chefão",
        "Pulp Fiction": "Pulp Fiction: Tempo de Violência",
        "The Dark Knight": "O Cavaleiro das Trevas",
        "Forrest Gump": "Forrest Gump: O Contador de Histórias",
        "Inception": "A Origem",
        "The Shawshank Redemption": "Um Sonho de Liberdade",
        "Schindler's List": "A Lista de Schindler",
        "The Lord of the Rings": "O Senhor dos Anéis",
        "Fight Club": "Clube da Luta",
        "Goodfellas": "Os Bons Companheiros",
        "The Silence of the Lambs": "O Silêncio dos Inocentes",
        "Saving Private Ryan": "O Resgate do Soldado Ryan",
        "The Green Mile": "À Espera de um Milagre",
        "Gladiator": "Gladiador",
        "Titanic": "Titanic",
        "Jurassic Park": "Parque dos Dinossauros",
        "The Lion King": "O Rei Leão",
        "Back to the Future": "De Volta para o Futuro",
        "Indiana Jones": "Indiana Jones",
        "E.T. the Extra-Terrestrial": "E.T.: O Extraterrestre",
        "The Terminator": "O Exterminador do Futuro",
        "Alien": "Alien: O Oitavo Passageiro",
        "Blade Runner": "Blade Runner: O Caçador de Androides",
        "Casablanca": "Casablanca",
        "Gone with the Wind": "E o Vento Levou",
        "Citizen Kane": "Cidadão Kane",
        "The Wizard of Oz": "O Mágico de Oz",
        "Psycho": "Psicose",
        "Vertigo": "Um Corpo que Cai",
        "Rear Window": "Janela Indiscreta",
        "North by Northwest": "Intriga Internacional",
        "The Shining": "O Iluminado",
        "The Exorcist": "O Exorcista",
        "Jaws": "Tubarão",
        "Rocky": "Rocky: Um Lutador",
        "Taxi Driver": "Taxi Driver",
        "Apocalypse Now": "Apocalypse Now",
        "The Deer Hunter": "O Caçador",
        "Platoon": "Platoon",
        "Full Metal Jacket": "Nascido para Matar",
        "Good Will Hunting": "Gênio Indomável",
        "American Beauty": "Beleza Americana",
        "The Sixth Sense": "O Sexto Sentido",
        "The Truman Show": "O Show de Truman",
        "The Big Lebowski": "O Grande Lebowski",
        "Pulp Fiction": "Pulp Fiction",
        "Reservoir Dogs": "Cães de Aluguel",
        "Jackie Brown": "Jackie Brown",
        "Kill Bill": "Kill Bill",
        "Inglourious Basterds": "Bastardos Inglórios",
        "Django Unchained": "Django Livre",
        "The Hateful Eight": "Os Oito Odiados",
        "Once Upon a Time in Hollywood": "Era Uma Vez em... Hollywood",
    }
    
    # Tenta encontrar correspondência parcial
    for english, portuguese in translations.items():
        if english in title:
            return title.replace(english, portuguese)
    
    return title

app = Flask(__name__, static_folder='frontend', template_folder='frontend')

# ================
# CONFIGURAÇÕES DE CAMINHO
# ================

ORIGINAL_DATA_PATH = os.path.join("data", "ratings.csv")
USER_RATINGS_PATH = os.path.join("data", "user_ratings.csv")

# Garante que o dataset de usuários exista
if not os.path.exists(USER_RATINGS_PATH):
    df_original = pd.read_csv(ORIGINAL_DATA_PATH, sep='\t', names=['user_id', 'movie_id', 'rating', 'timestamp'])
    df_original.to_csv(USER_RATINGS_PATH, sep='\t', index=False, header=False)

# Carrega dicionário de nomes dos filmes
MOVIE_NAMES = load_movie_names("data")

# Inicializa o recomendador
try:
    recommender = MovieRecommender(USER_RATINGS_PATH)
    print("✅ Modelo carregado e treinado com sucesso!")
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
    """Retorna lista de filmes para o frontend (com títulos em português)"""
    try:
        movie_list = []
        for movie_id, title in MOVIE_NAMES.items():
            # Traduz o título para português
            translated_title = translate_movie_title(title)
            movie_list.append({
                "movie_id": int(movie_id),
                "title": translated_title
            })
        
        # Ordena por título
        movie_list.sort(key=lambda x: x["title"])
        
        return jsonify(movie_list)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/recommend/<int:user_id>")
def recommend(user_id):
    """Retorna recomendações para um usuário"""
    if not recommender:
        return jsonify({"error": "Modelo não carregado."}), 500

    try:
        recommendations = recommender.recommend_for_user(user_id, n=15)  # 15 filmes como no Lovable
        rec_with_details = []
        for movie_id, rating in recommendations:
            title = MOVIE_NAMES.get(int(movie_id), f"Filme {movie_id}")
            poster = get_movie_poster(title)
            rec_with_details.append({
                "movie_id": int(movie_id),
                "title": title,
                "poster": poster,
                "predicted_rating": float(rating)
            })
        return jsonify({
            "user_id": user_id,
            "recommendations": rec_with_details
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/submit_ratings", methods=["POST"])
def submit_ratings():
    """Recebe avaliações, salva, e retorna recomendações personalizadas"""
    try:
        user_id = int(request.form.get("user_id"))
        movies = []
        
        for i in range(1, 4):  # 3 filmes
            movie_id = request.form.get(f"movie_id_{i}")
            rating = request.form.get(f"rating_{i}")
            if movie_id and rating:
                movies.append({
                    "user_id": user_id,
                    "movie_id": int(movie_id),
                    "rating": float(rating),
                    "timestamp": int(time.time())
                })

        if not movies:
            return jsonify({"error": "Nenhum filme enviado"}), 400

        # Salva avaliações
        df_new = pd.DataFrame(movies)
        df_new.to_csv(USER_RATINGS_PATH, sep='\t', mode='a', header=False, index=False)

        # Recarrega modelo
        global recommender
        recommender = MovieRecommender(USER_RATINGS_PATH)

        # Gera recomendações (15 filmes)
        recommendations = recommender.recommend_for_user(user_id, n=15)

        # Adiciona detalhes
        rec_with_details = []
        for movie_id, rating in recommendations:
            title = MOVIE_NAMES.get(int(movie_id), f"Filme {movie_id}")
            poster = get_movie_poster(title)
            rec_with_details.append({
                "movie_id": int(movie_id),
                "title": title,
                "poster": poster,
                "predicted_rating": float(rating)
            })

        return jsonify({
            "message": "✅ Avaliações salvas e recomendações geradas!",
            "user_id": user_id,
            "recommendations": rec_with_details
        })

    except Exception as e:
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

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
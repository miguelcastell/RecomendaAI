# models/recommendation.py
import random
import json
import os

class MovieRecommender:
    def __init__(self, data_path="data/tmdb_movies.json"):
        self.data_path = data_path
        self.movies = self.load_movies()
        print(f"🎬 Inicializado com {len(self.movies)} filmes disponíveis")
    
    def load_movies(self):
        """Carrega filmes do JSON ou usa fallback"""
        try:
            if os.path.exists(self.data_path):
                with open(self.data_path, 'r', encoding='utf-8') as f:
                    movies = json.load(f)
                    if len(movies) > 0:
                        print(f"✅ Carregou {len(movies)} filmes do arquivo {self.data_path}")
                        return movies
                    else:
                        print("⚠️ Arquivo JSON vazio")
            else:
                print(f"⚠️ Arquivo não encontrado: {self.data_path}")
        except Exception as e:
            print(f"❌ Erro ao carregar JSON: {e}")
        
        # Fallback - filmes hardcoded
        print("🔄 Usando dataset de fallback")
        return [
            {"id": 278, "title": "Um Sonho de Liberdade", "vote_average": 9.3, "poster_path": "/q6y0Go1tsGEsmtFryDOJo3dEmqu.jpg"},
            {"id": 238, "title": "O Poderoso Chefão", "vote_average": 9.2, "poster_path": "/3bhkrj58Vtu7enYsRolD1fZdja1.jpg"},
            {"id": 424, "title": "Batman: O Cavaleiro das Trevas", "vote_average": 9.0, "poster_path": "/qJ2tW6WMUDux911r6m7haRef0WH.jpg"},
            {"id": 597, "title": "Pulp Fiction: Tempo de Violência", "vote_average": 8.9, "poster_path": "/d5iIlFn5s0ImszYzBPb8JPIfbXD.jpg"},
            {"id": 122, "title": "Forrest Gump: O Contador de Histórias", "vote_average": 8.8, "poster_path": "/arw2vcBveWOVZr6pxd9XTd1TdQa.jpg"},
            {"id": 121, "title": "Gladiador", "vote_average": 8.5, "poster_path": "/fm6KqXpk3M2HVveHwCrBSSBaO0V.jpg"},
            {"id": 680, "title": "Clube da Luta", "vote_average": 8.8, "poster_path": "/pB8BM7pdSp6B6Ih7QZ4DrQ3PmJK.jpg"},
            {"id": 120, "title": "A Lista de Schindler", "vote_average": 8.6, "poster_path": "/sF1U4EUQS8YHUYjNl3pMGNIQyr0.jpg"},
            {"id": 572151, "title": "Homem-Aranha: Através do Aranhaverso", "vote_average": 8.7, "poster_path": "/8Vt6mWEReuy4Of61Lnj5Xj704m8.jpg"},
            {"id": 634649, "title": "Homem-Aranha: Sem Volta Para Casa", "vote_average": 8.4, "poster_path": "/uJYYizSuA9Y3DCs0qS4qWvHfZg4.jpg"}
        ]
    
    def recommend_for_user(self, user_id, n=15):
        """Recomenda filmes populares"""
        if not self.movies:
            print("❌ Nenhum filme disponível para recomendação")
            return []
        
        print(f"🎲 Gerando {n} recomendações aleatórias...")
        movies_copy = self.movies.copy()
        random.shuffle(movies_copy)
        recommendations = []
        
        for movie in movies_copy[:n]:
            title = movie.get('title', f"Filme {movie['id']}")
            poster = "https://placehold.co/200x300/141414/FFFFFF?font=roboto&text=Sem+Poster"
            
            if movie.get('poster_path'):
                poster = f"https://image.tmdb.org/t/p/w500{movie['poster_path']}"
            
            recommendations.append((
                movie['id'],
                movie.get('vote_average', 7.5),
                title,
                poster
            ))
        
        print(f"✅ Gerou {len(recommendations)} recomendações")
        return recommendations
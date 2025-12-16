import random
import json
import os
from collections import Counter

class MovieRecommender:
    def __init__(self, data_path="data/tmdb_movies.json"):
        self.data_path = data_path
        self.movies = self.load_movies()
        print(f"🎬 Inicializado com {len(self.movies)} filmes")
    
    def load_movies(self):
        """Carrega filmes com fallback garantido"""
        try:
            if os.path.exists(self.data_path):
                with open(self.data_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        movies = json.loads(content)
                        for movie in movies:
                            if 'genres' not in movie:
                                movie['genres'] = []
                        if len(movies) > 0:
                            print("✅ Carregou filmes do JSON")
                            return movies
            print("⚠️ JSON vazio ou inválido")
        except Exception as e:
            print(f"❌ Erro ao carregar JSON: {e}")
        
        print("🔄 Usando fallback com gêneros")
        return [
            {"id": 1, "title": "Homem-Aranha: Sem Volta Para Casa", "vote_average": 8.4, "poster_path": "/uJYYizSuA9Y3DCs0qS4qWvHfZg4.jpg", "genres": ["Ação", "Aventura", "Ficção Científica"]},
            {"id": 2, "title": "Vingadores: Ultimato", "vote_average": 8.7, "poster_path": "/or06FN3Dka5tukK1e9sl16pB3iy.jpg", "genres": ["Ação", "Aventura", "Ficção Científica"]},
            {"id": 3, "title": "Tropa de Elite 2", "vote_average": 8.1, "poster_path": "/tjZaFgCk3GRK3K9m7k1J9Q9x9XH.jpg", "genres": ["Ação", "Drama", "Crime"]},
            {"id": 4, "title": "Cidade de Deus", "vote_average": 8.6, "poster_path": "/lT4l5tD7ohRJjNL1iZB5KXNkxQN.jpg", "genres": ["Drama", "Crime"]},
            {"id": 5, "title": "O Auto da Compadecida", "vote_average": 8.5, "poster_path": "/b3T0V86iF9C5YsYRqPjWZ2Fk7XQ.jpg", "genres": ["Comédia", "Drama", "Fantasia"]},
            {"id": 6, "title": "Parasita", "vote_average": 8.6, "poster_path": "/7IiTTgloJzvGI1TAYymCfbfl3vF.jpg", "genres": ["Drama", "Thriller"]},
            {"id": 7, "title": "Coringa", "vote_average": 8.4, "poster_path": "/udDclJoHjfjb8Ekgsd4FDteOkCU.jpg", "genres": ["Crime", "Drama", "Thriller"]},
            {"id": 8, "title": "Interestelar", "vote_average": 8.6, "poster_path": "/gEU2QniE6E77NI6lCU6MxlNBvIx.jpg", "genres": ["Aventura", "Drama", "Ficção Científica"]},
            {"id": 9, "title": "Django Livre", "vote_average": 8.4, "poster_path": "/k0lNOD4mOKk4kCQKlK7lGgJzBpX.jpg", "genres": ["Drama", "Faroeste"]},
            {"id": 10, "title": "Matrix", "vote_average": 8.7, "poster_path": "/f89U3ADr1oiB1s9GkdPOEpXUk5H.jpg", "genres": ["Ação", "Ficção Científica"]}
        ]
    
    def recommend_for_user(self, user_id, n=15, selected_movie_ids=None):
        """Recomenda filmes baseado nos gêneros dos filmes selecionados"""
        if not self.movies:
            return []
        
        if not selected_movie_ids:
            movies_copy = self.movies.copy()
            random.shuffle(movies_copy)
            recommendations = []
            for movie in movies_copy[:n]:
                title = movie.get('title', f"Filme {movie['id']}")
                poster = f"https://image.tmdb.org/t/p/w500{movie.get('poster_path', '')}" if movie.get('poster_path') else "https://placehold.co/200x300/141414/FFFFFF?font=roboto&text=Sem+Poster"
                recommendations.append((
                    movie['id'],
                    movie.get('vote_average', 7.5),
                    title,
                    poster
                ))
            return recommendations
        
        selected_genres = []
        for movie_id in selected_movie_ids:
            for movie in self.movies:
                if movie['id'] == movie_id:
                    selected_genres.extend(movie.get('genres', []))
                    break
        
        if not selected_genres:
            return self.recommend_for_user(user_id, n)
        
        genre_counter = Counter(selected_genres)
        top_genres = [genre for genre, count in genre_counter.most_common(3)]
        
        print(f"🎯 Gêneros preferidos: {top_genres}")
        
        matching_movies = []
        for movie in self.movies:
            movie_genres = movie.get('genres', [])
            if any(genre in movie_genres for genre in top_genres):
                matching_movies.append(movie)
        
        if not matching_movies:
            matching_movies = self.movies
        
        random.shuffle(matching_movies)
        recommendations = []
        for movie in matching_movies[:n]:
            title = movie.get('title', f"Filme {movie['id']}")
            poster = f"https://image.tmdb.org/t/p/w500{movie.get('poster_path', '')}" if movie.get('poster_path') else "https://placehold.co/200x300/141414/FFFFFF?font=roboto&text=Sem+Poster"
            recommendations.append((
                movie['id'],
                movie.get('vote_average', 7.5),
                title,
                poster
            ))
        
        return recommendations
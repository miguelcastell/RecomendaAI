# models/recommendation.py
import random

class MovieRecommender:
    def __init__(self, data_path="data/tmdb_movies.json"):
        self.data_path = data_path
        self.movies = self.load_movies()
    
    def load_movies(self):
        import json
        try:
            with open(self.data_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    
    def recommend_for_user(self, user_id, n=15):
        """Recomenda filmes populares (versão simplificada)"""
        if not self.movies:
            return []
        
        # Embaralha e retorna n filmes
        movies_copy = self.movies.copy()
        random.shuffle(movies_copy)
        recommendations = []
        
        for movie in movies_copy[:n]:
            recommendations.append((
                movie['id'],
                movie['vote_average']  # Usa a nota do TMDB como "predicted_rating"
            ))
        
        return recommendations
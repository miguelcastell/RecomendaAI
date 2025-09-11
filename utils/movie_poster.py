# utils/movie_poster.py
import os
from functools import lru_cache

@lru_cache(maxsize=1000)
def get_movie_poster(title):
    """
    Busca o pôster de um filme pelo título (USANDO APENAS TMDB)
    """
    try:
        from utils.movie_loader import load_movies_data
        movies = load_movies_data()
        
        for movie in movies:
            if movie['title'] == title:
                if movie.get('poster_path'):
                    # URL pública do TMDB - NÃO PRECISA DE CHAVE!
                    return f"https://image.tmdb.org/t/p/w500{movie['poster_path']}"
                else:
                    # Fallback se o filme não tiver pôster
                    return "https://placehold.co/200x300/141414/FFFFFF?font=roboto&text=Sem+Poster"
        # Fallback se o filme não for encontrado
        return "https://placehold.co/200x300/141414/FFFFFF?font=roboto&text=Filme+Não+Encontrado"
    except Exception as e:
        print(f"Erro ao buscar pôster para '{title}': {e}")
        # Fallback em caso de erro
        return "https://placehold.co/200x300/141414/FFFFFF?font=roboto&text=Erro"
# utils/fetch_tmdb_movies.py
import requests
import json
import time
import os

# Substitua pela sua chave TMDB
import os
TMDB_API_KEY = os.getenv("TMDB_API_KEY", "chave_fallback_para_desenvolvimento_local")

def fetch_movies_by_genre(genre_id, page=1):
    """Busca filmes por gênero"""
    url = "https://api.themoviedb.org/3/discover/movie"
    params = {
        'api_key': TMDB_API_KEY,
        'language': 'pt-BR',
        'sort_by': 'popularity.desc',
        'page': page,
        'with_genres': genre_id,
        'vote_count.gte': 50,
        'vote_average.gte': 6.0
    }
    
    response = requests.get(url, params=params)
    return response.json()

def fetch_movie_details(movie_id):
    """Busca detalhes completos de um filme"""
    url = f"https://api.themoviedb.org/3/movie/{movie_id}"
    params = {
        'api_key': TMDB_API_KEY,
        'language': 'pt-BR',
        'append_to_response': 'credits,keywords,genres'
    }
    
    response = requests.get(url, params=params)
    return response.json()

def generate_large_dataset():
    """Gera dataset grande com filmes de vários gêneros"""
    all_movies = []
    movie_ids = set()
    
    # IDs de gêneros populares
    genres = {
        28: "Ação",
        12: "Aventura", 
        35: "Comédia",
        80: "Crime",
        99: "Documentário",
        18: "Drama",
        10751: "Família",
        14: "Fantasia",
        36: "História",
        27: "Terror",
        10402: "Música",
        9648: "Mistério",
        10749: "Romance",
        878: "Ficção Científica",
        10770: "Cinema TV",
        53: "Thriller",
        10752: "Guerra",
        37: "Faroeste"
    }
    
    print("🔍 Buscando filmes em português-BR...")
    
    # Busca 3 páginas por gênero (cerca de 60 filmes por gênero)
    for genre_id, genre_name in genres.items():
        print(f"🎬 Buscando filmes de {genre_name}...")
        for page in range(1, 4):
            print(f"📄 Página {page}/3...")
            data = fetch_movies_by_genre(genre_id, page)
            
            for movie in data.get('results', []):
                movie_id = movie['id']
                if movie_id in movie_ids:
                    continue
                
                movie_ids.add(movie_id)
                details = fetch_movie_details(movie_id)
                
                # Extrai gêneros
                genres_list = [genre['name'] for genre in details.get('genres', [])]
                
                # Cria entrada do dataset
                movie_entry = {
                    'id': movie_id,
                    'title': details.get('title', movie.get('title', 'Sem título')),
                    'original_title': movie.get('original_title', ''),
                    'overview': details.get('overview', ''),
                    'release_date': details.get('release_date', ''),
                    'vote_average': details.get('vote_average', 0),
                    'vote_count': details.get('vote_count', 0),
                    'genres': genres_list,
                    'poster_path': details.get('poster_path', ''),
                    'backdrop_path': details.get('backdrop_path', '')
                }
                
                all_movies.append(movie_entry)
                time.sleep(0.1)  # Evita rate limiting
            
            time.sleep(0.3)
    
    # Salva dataset
    with open('data/tmdb_movies_large.json', 'w', encoding='utf-8') as f:
        json.dump(all_movies, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Dataset gigante gerado com {len(all_movies)} filmes!")
    return all_movies

if __name__ == "__main__":
    generate_large_dataset()
# utils/fetch_tmdb_movies.py
import requests
import json
import time
import os

# Substitua pela sua chave TMDB
TMDB_API_KEY = "sua_chave_tmdb_aqui"

def fetch_popular_movies(page=1):
    """Busca filmes populares em português do Brasil"""
    url = "https://api.themoviedb.org/3/discover/movie"
    params = {
        'api_key': TMDB_API_KEY,
        'language': 'pt-BR',
        'sort_by': 'popularity.desc',
        'page': page,
        'vote_count.gte': 100,  # Só filmes com pelo menos 100 votos
        'vote_average.gte': 6.0  # Só filmes com nota >= 6.0
    }
    
    response = requests.get(url, params=params)
    return response.json()

def fetch_movie_details(movie_id):
    """Busca detalhes de um filme específico"""
    url = f"https://api.themoviedb.org/3/movie/{movie_id}"
    params = {
        'api_key': TMDB_API_KEY,
        'language': 'pt-BR',
        'append_to_response': 'credits,keywords'
    }
    
    response = requests.get(url, params=params)
    return response.json()

def save_movies_to_json(movies, filename="data/tmdb_movies.json"):
    """Salva filmes em arquivo JSON"""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(movies, f, ensure_ascii=False, indent=2)

def generate_dataset():
    """Gera dataset completo de filmes populares"""
    all_movies = []
    movie_ids = set()
    
    print("🔍 Buscando filmes populares em português...")
    
    # Busca 5 páginas de filmes (cerca de 100 filmes)
    for page in range(1, 6):
        print(f"📄 Página {page}/5...")
        data = fetch_popular_movies(page)
        
        for movie in data.get('results', []):
            movie_id = movie['id']
            if movie_id in movie_ids:
                continue
                
            movie_ids.add(movie_id)
            details = fetch_movie_details(movie_id)
            
            # Extrai gêneros
            genres = [genre['name'] for genre in details.get('genres', [])]
            
            # Extrai elenco principal
            cast = [actor['name'] for actor in details.get('credits', {}).get('cast', [])[:5]]
            
            # Cria entrada do dataset
            movie_entry = {
                'id': movie_id,
                'title': details.get('title', movie.get('title', 'Sem título')),
                'original_title': movie.get('original_title', ''),
                'overview': details.get('overview', ''),
                'release_date': details.get('release_date', ''),
                'vote_average': details.get('vote_average', 0),
                'vote_count': details.get('vote_count', 0),
                'genres': genres,
                'cast': cast,
                'poster_path': details.get('poster_path', ''),
                'backdrop_path': details.get('backdrop_path', '')
            }
            
            all_movies.append(movie_entry)
            time.sleep(0.2)  # Evita rate limiting
        
        time.sleep(0.5)
    
    # Salva dataset
    save_movies_to_json(all_movies)
    print(f"✅ Dataset gerado com {len(all_movies)} filmes!")
    return all_movies

if __name__ == "__main__":
    generate_dataset()
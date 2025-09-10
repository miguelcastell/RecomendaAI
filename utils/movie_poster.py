# utils/movie_poster.py
import requests
import time
import os
from functools import lru_cache

# Substitua pela sua chave OMDb
OMDB_API_KEY = os.getenv("OMDB_API_KEY", "sua_chave_omdb_aqui")

@lru_cache(maxsize=1000)
def get_movie_poster(title):
    """
    Busca o pôster de um filme pelo título usando OMDb API
    Retorna URL da imagem ou imagem padrão se não encontrar
    """
    if OMDB_API_KEY == "sua_chave_omdb_aqui":
        return "https://via.placeholder.com/200x300?text=Sem+Poster"

    try:
        # Remove ano entre parênteses: "Toy Story (1995)" → "Toy Story"
        clean_title = title.split(" (")[0] if " (" in title else title
        
        url = f"http://www.omdbapi.com/"
        params = {
            't': clean_title,
            'apikey': OMDB_API_KEY
        }
        
        response = requests.get(url, params=params, timeout=5)
        data = response.json()
        
        if data.get('Response') == 'True' and data.get('Poster') != 'N/A':
            return data['Poster']
        else:
            return "https://via.placeholder.com/200x300?text=Poster+Indispon%C3%ADvel"
            
    except Exception as e:
        print(f"Erro ao buscar pôster para '{title}': {e}")
        return "https://via.placeholder.com/200x300?text=Erro"

# Cache para evitar requisições repetidas
POSTER_CACHE = {}
# models/recommendation.py
import pandas as pd
from surprise import Dataset, Reader, SVD
from surprise.model_selection import train_test_split

class MovieRecommender:
    def __init__(self, data_path):
        self.data_path = data_path
        self.model = SVD()
        self.trainset = None
        self.load_and_train()

    def load_and_train(self):
        # Aqui a função vai carregar os dados (separados por TAB)
        df = pd.read_csv(self.data_path, sep='\t', names=['user_id', 'movie_id', 'rating', 'timestamp'])
        
        # Essa parte é uma preparação para a lib Surprise
        reader = Reader(rating_scale=(1, 5))
        data = Dataset.load_from_df(df[['user_id', 'movie_id', 'rating']], reader)
        
        # Divide e treina
        trainset, _ = train_test_split(data, test_size=0.2)
        self.trainset = trainset
        self.model.fit(trainset)
        print(f"✅ Modelo treinado com {len(df)} avaliações.")

    def recommend_for_user(self, user_id, n=5):
        # Pega todos os filmes que o usuário NÃO avaliou
        all_movies = self.trainset.build_anti_testset()
        user_movies = [item for item in all_movies if item[0] == user_id]
        
        # Faz predições
        predictions = self.model.test(user_movies)
        
        # Ordena por rating previsto (do maior pro menor)
        predictions.sort(key=lambda x: x.est, reverse=True)
        
        # Retorna os top N
        return [(pred.iid, pred.est) for pred in predictions[:n]]
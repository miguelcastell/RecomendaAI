<h1 align="center">🤖 Bem-vindo ao RecomendaAí!</h1>

<p align="center">
<em>Seu assistente pessoal para descobrir filmes incríveis, feito com Python e Machine Learning.</em>
<br/>
<br/>
<a href="#-sobre-o-projeto">Ver Funcionalidades</a> •
<a href="#-tecnologias-utilizadas">Ver Tech Stack</a> •
<a href="#-como-executar-localmente">Rodar Localmente</a>
</p>

# Sobre o Projeto
O RecomendaAí é um sistema de recomendação de filmes construído em Python, que combina um back-end robusto com técnicas de Machine Learning para oferecer sugestões personalizadas com base nas avaliações dos usuários.

## Este projeto foi desenvolvido com o objetivo de:

✅ Aprimorar habilidades em Python, APIs e bancos de dados

✅ Aplicar conceitos reais de Machine Learning (especificamente Sistemas de Recomendação)

✅ Criar uma aplicação completa, do zero, com potencial de evolução e deploy

✅ Montar um portfólio técnico que demonstra domínio de múltiplas camadas de desenvolvimento

## Funcionalidades
✅ Sistema de recomendação baseado em filtro colaborativo

✅ API REST com Flask para interagir com o modelo

✅ Banco de dados SQLite para persistência de avaliações

✅ Dataset real do MovieLens (100k avaliações)

✅ Modelo treinado com a biblioteca Surprise (SVD)

## Tecnologias Utilizadas
<p align="left">
<a href="https://skillicons.dev">
<img src="https://skillicons.dev/icons?i=python,flask,pandas,numpy,scikitlearn,sqlite&perline=6" />
</a>
</p>

📂 Estrutura do Projeto
recomenda_ai/
├── app.py                  # Ponto de entrada da API
├── models/
│   └── recommendation.py   # Lógica do modelo de ML
├── data/
│   └── ratings.csv         # Dataset de avaliações
├── database/
│   └── db.py               # Conexão com SQLite
├── requirements.txt        # Dependências
└── README.md               # Este arquivo!

# 🚀 Como Executar Localmente
## 1. Clone o repositório
git clone https://github.com/seu-usuario/recomenda_ai.git
cd recomenda_ai

## 2. Crie e ative um ambiente virtual
python -m venv venv
source venv/bin/activate      # Linux/Mac
ou
venv\Scripts\activate         # Windows

## 3. Instale as dependências
pip install -r requirements.txt

## 4. Execute a aplicação
python app.py

# 📈 Próximos Passos
[ ] Interface web com Jinja2 ou React

[ ] Sistema de login de usuários

[ ] Recomendação híbrida (conteúdo + colaborativo)

[ ] Deploy com Docker + Render/Railway

[ ] Integração com API do TMDB para posters e sinopses

# 🤝 Contribuições
Sinta-se à vontade para abrir issues ou pull requests! Toda contribuição que melhore o código, a documentação ou as funcionalidades é bem-vinda.

# 📬 Contato
Desenvolvido com 💥 por Miguel Mantoan Castellani | LinkedIn | Email

"Não sabe o que assistir hoje? O RecomendaAí sabe."

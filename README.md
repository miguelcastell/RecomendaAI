<h1 align="left">🎬 RecomendAI — Seu Assistente Pessoal de Filmes </h1>
"Porque escolher o que assistir nunca foi tão fácil — e tão personalizado.”

<p align="left">
  <em>Seu assistente pessoal pra descobrir filmes incríveis, feito com Python, Machine Learning e muito ❤️.</em>
  <br/>
  <br/>
  <a href="#-sobre-o-projeto">Ver Funcionalidades</a> •
  <a href="#-tecnologias-utilizadas">Ver Tech Stack</a> •
  <a href="#-como-executar">Rodar Localmente</a>
</p>

---

## 🚀 Sobre o Projeto

O **RecomendAI** é um sistema inteligente de recomendação de filmes que combina **Python, Machine Learning e uma interface web moderna** para oferecer sugestões personalizadas com base nos seus filmes favoritos.

> ✅ **Sem complicações:** Você só digita 3 filmes que AMA — o sistema faz o resto.  
> ✅ **Filmes em português:** Dataset atualizado com filmes brasileiros e internacionais recentes.  
> ✅ **Design premium:** Interface inspirada em plataformas de streaming, com autocomplete inteligente.  
> ✅ **100% funcional:** Do back-end em Flask ao front-end responsivo — tudo integrado e pronto pra uso.

---

## ⚙️ Funcionalidades

✅ **Autocomplete inteligente** — digite e veja sugestões em tempo real  
✅ **Recomendações personalizadas** — baseadas nos seus filmes favoritos  
✅ **Dataset em português** — filmes brasileiros e internacionais atualizados (via TMDB)  
✅ **Interface responsiva** — funciona perfeitamente em desktop e mobile  
✅ **Sistema de notas automático** — você só escolhe filmes, o sistema assume que você AMA todos (nota 5 ⭐)  
✅ **Recomendação por gênero** — o sistema identifica seus gêneros preferidos e recomenda filmes alinhados

---

## 🛠️ Tecnologias Utilizadas

<p align="left">
  <a href="https://skillicons.dev">
    <img src="https://skillicons.dev/icons?i=python,flask,html,css,js,json,git&perline=7" />
  </a>
</p>

---

## 📂 Estrutura do Projeto

```
RecomendaAI/
├── app.py                  # Ponto de entrada da API (Flask)
├── models/
│   └── recommendation.py   # Lógica de recomendação por gênero
├── data/
│   └── tmdb_movies_large.json  # Dataset de +600 filmes em português-BR
├── utils/
│   ├── fetch_tmdb_movies.py    # Script pra gerar/atualizar o dataset
│   ├── movie_loader.py         # Carrega nomes e dados dos filmes
│   └── movie_poster.py         # Busca pôsteres via TMDB (sem API key!)
├── frontend/
│   ├── index.html          # Interface principal (autocomplete + cards)
│   └── style.css           # Estilo moderno e responsivo
├── requirements.txt        # Dependências
├── runtime.txt             # Força Python 3.11 (pra evitar erros)
└── README.md               # Este arquivo!
```

---

## 🚀 Como Executar Localmente

### 1. Clone o repositório

```bash
git clone https://github.com/miguelcastell/RecomendaAI.git
cd RecomendaAI
```

### 2. Crie e ative o ambiente virtual

```bash
python -m venv venv
source venv/bin/activate      # Linux/Mac
# ou
venv\Scriptsctivate         # Windows
```

### 3. Instale as dependências

```bash
pip install -r requirements.txt
```

### 4. (Opcional) Gere/atualize o dataset de filmes

> ⚠️ Você precisa de uma chave API gratuita do TMDB.

```bash
# Substitua "sua_chave_aqui" no utils/fetch_tmdb_movies.py
python utils/fetch_tmdb_movies.py
```

### 5. Execute a aplicação

```bash
python app.py
```

### 6. Acesse no navegador

👉 http://localhost:5000

---

## 🎥 Demonstração

### Tela Inicial
<img width="1889" height="732" alt="image" src="https://github.com/user-attachments/assets/1de54446-95b5-4a59-901e-9b23797c9d65" />





### Recomendações Geradas
<img width="1614" height="854" alt="image" src="https://github.com/user-attachments/assets/40cfbfdb-eb1b-4d4a-af84-313cc34aaf25" />


---

## 📈 Próximos Passos (Futuro)

- [ ] Implementar recomendação por gênero e ano  
- [ ] Adicionar mais filmes brasileiros específicos  
- [ ] Fazer deploy na nuvem (Railway, Vercel)  
- [ ] Criar sistema de histórico de recomendações  
- [ ] Adicionar compartilhamento de listas  
- [ ] Migrar de SQLite para PostgreSQL  
- [ ] Adicionar sistema de login (JWT)

---

## 🤝 Contribuições

Sinta-se à vontade para abrir *issues* ou *pull requests*! Toda contribuição que melhore o código, a documentação ou as funcionalidades é bem-vinda.

---

## 📬 Contato

Desenvolvido com 💥 por **Miguel Castell**  
[![LinkedIn]([https://img.shields.io/badge/LinkedIn-0077B5?style=for-the-badge&logo=linkedin&logoColor=white)](https://linkedin.com/in/seu-perfil](https://www.linkedin.com/in/miguel-mantoan-castellani-744304324))  
[![GitHub]([https://img.shields.io/badge/GitHub-100000?style=for-the-badge&logo=github&logoColor=white)](https://github.com/miguelcastell](https://github.com/miguelcastell))

---

> *“Não sabe o que assistir hoje? O RecomendAI sabe.”*

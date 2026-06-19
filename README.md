# 🎬 RecomendAI — Inteligência Artificial e Recuperação de Informação

![Status](https://img.shields.io/badge/status-funcional-success)
![Python](https://img.shields.io/badge/python-3.11-blue)
![Machine Learning](https://img.shields.io/badge/ML-Hybrid-orange)
![SRI](https://img.shields.io/badge/SRI-TF--IDF-blueviolet)

O **RecomendAI** é um ecossistema completo de recomendação de filmes que utiliza técnicas avançadas de **Recuperação de Informação (SRI)** e **Machine Learning (ML)** para entregar sugestões personalizadas com precisão cirúrgica.

---

## 🧠 Arquitetura Tecnológica

Diferente de sistemas simples baseados apenas em tags, o RecomendAI opera através de um motor híbrido de duas camadas:

### 1. Sistema de Recuperação de Informação (SRI)
A primeira camada atua na **recuperação de candidatos**. Utilizamos o **Modelo de Espaço Vetorial** para indexar os filmes:
*   **Indexação Semântica (TF-IDF):** Transformamos as sinopses e gêneros em vetores numéricos. O algoritmo *Term Frequency-Inverse Document Frequency* pondera a relevância das palavras, permitindo que o sistema entenda temas profundos além das categorias óbvias.
*   **Métrica de Similaridade (Cosine Similarity):** A busca por filmes similares é feita calculando o cosseno do ângulo entre os vetores de conteúdo, recuperando instantaneamente os itens mais próximos no espaço vetorial.

### 2. Machine Learning (ML)
A segunda camada realiza o **Ranking e Predição**. 
*   **Filtragem Colaborativa (SVD):** Utilizamos o algoritmo *Singular Value Decomposition* para prever a nota que um usuário daria a um filme específico, baseando-se em padrões comportamentais latentes.
*   **Motor Híbrido:** O sistema combina a relevância temática do SRI com a predição personalizada do ML para re-rankear os resultados, garantindo que as recomendações sejam tecnicamente parecidas e pessoalmente interessantes.

---

## ⚙️ Funcionalidades Principais

*   **Treinamento Via Notebook:** Ambiente Jupyter completo para análise de dados e retreino de modelos (`research/train_model.ipynb`).
*   **Persistência de Dados:** Integração com SQLite via SQLAlchemy para armazenar o histórico de preferências dos usuários.
*   **Motor Otimizado:** Carregamento de pesos pré-treinados (`.pkl`) para respostas em milissegundos.
*   **Interface Web Moderna:** Frontend responsivo com autocomplete inteligente conectado diretamente ao índice de filmes.

---

## 📂 Estrutura do Projeto

```
RecomendaAI/
├── app.py                  # Backend Flask com persistência SQL
├── models/
│   ├── recommendation.py   # Motor Híbrido (SRI + ML)
│   └── weights/            # Modelos treinados (.pkl)
├── research/
│   ├── train_model.ipynb   # Notebook de treinamento e experimentos
│   └── evaluate_sri.ipynb  # Notebook de avaliação de acurácia e eficiência do SRI
├── database/
│   └── models.py           # Esquema do banco de dados (User Ratings)
├── data/
│   └── tmdb_movies_large.json  # Dataset de metadados da TMDB
└── frontend/               # UI/UX do sistema
```

---

## 🚀 Como Executar e Treinar

### 1. Instalação
```bash
pip install -r requirements.txt
```

### 2. Treinamento do Modelo
Para gerar ou atualizar o "cérebro" do sistema:
1. Abra o arquivo `research/train_model.ipynb`.
2. Execute todas as células para gerar os arquivos de pesos necessários em `models/weights/`.

> [!IMPORTANT]
> Como a pasta `models/weights/` está adicionada ao `.gitignore` (para não subir arquivos binários ao GitHub), você **precisa** executar o notebook pelo menos uma vez antes de rodar o servidor `app.py` pela primeira vez para gerar os arquivos de peso.

### 3. Execução do Servidor
```bash
python app.py
```
Acesse: `http://localhost:5000`

### 4. Avaliação de Métricas (Acurácia e Eficiência)
Para mensurar a qualidade e a performance do Sistema de Recuperação de Informação (SRI):
1. Abra o notebook `research/evaluate_sri.ipynb`.
2. Execute o código de teste para calcular a **Precisão em K (Precision@K)** (que afere a eficácia cruzando gêneros semelhantes) e o **Tempo Médio de Resposta** por consulta (que mede a latência em milissegundos).

---

## 📈 Pipeline de Dados

1.  **Coleta:** O usuário seleciona filmes favoritos na interface.
2.  **Armazenamento:** O sistema salva as preferências como notas implícitas no Banco de Dados.
3.  **Processamento:** O Notebook consome esses dados para retreinar o SVD.
4.  **Entrega:** O motor híbrido utiliza os novos pesos para refinar as futuras recomendações.

---

## 🤝 Contribuições e Contato

Desenvolvido por **Miguel Castellani**  
[![LinkedIn](https://img.shields.io/badge/LinkedIn-0077B5?style=for-the-badge&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/miguel-mantoan-castellani-744304324)
[![GitHub](https://img.shields.io/badge/GitHub-100000?style=for-the-badge&logo=github&logoColor=white)](https://github.com/miguelcastell)

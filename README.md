# 🎶 AI Hybrid Music Recommender

> ACLARACION: Este proyecto fue realizado con la IA de AntiGravity y un uso correcto de prompts para llegar a un resultado optimo y funcional, yo solo me encargue de la logica y la implementacion de la IA, a traves de conocimientos obtenidos en cursos de desarrollo con IA y programacion. 


> Un Sistema de Recomendación de Música Avanzado, impulsado por Inteligencia Artificial y Geometría Vectorial, que calcula el "ADN Acústico" sobre un Universo de 1.2 Millones de Canciones.

![AI Engine](https://img.shields.io/badge/AI_Engine-NumPy_Vectors-blue?style=for-the-badge&logo=python)
![Architecture](https://img.shields.io/badge/Architecture-FastAPI%20%2B%20Vanilla_JS-emerald?style=for-the-badge&logo=fastapi)
![Data Scale](https://img.shields.io/badge/Dataset-1.2M_Tracks-purple?style=for-the-badge&logo=databricks)
![Status](https://img.shields.io/badge/Status-Production_Ready-success?style=for-the-badge)

## 🧠 ¿Cómo Funciona la Inteligencia Artificial?

A diferencia de recomendadores básicos, este motor no utiliza simples "Tags" de género. Extrae y calcula las distancias Euclidianas usando **9 Variables Acústicas (DNA Dimensions)**:
* `Valence`, `Energy`, `Danceability`, `Acousticness`, `Liveness`, `Speechiness`, `Tempo`, `Instrumentalness`, `Loudness`.

### ⚡ Modelo de Puntuación Híbrido Ponderado (Hybrid Scoring)
El núcleo utiliza una arquitectura de *Weighted Composite Scoring*:
```python
Hybrid_Rank = (Acoustic_DNA_Match * 0.50) + (Global_Popularity * 0.50)
```
La red captura algoritmicamente una colisión balanceada (Stateless) donde compiten las 1,200,000 pistas, evaluando de forma simultánea precisión geométrica contra el prestigio global del artista.

## ✨ Características Principales

- 🚀 **Performance a Velocidad Caché L1:** Los cálculos hiper-dimensionales corren en fracciones de milisegundos nativos usando C-backend de NumPy, eliminando la necesidad de robustas BD vectoriales externas.
- 🕷️ **Chart.js Radar Dinámico:** Genera en tiempo real un gráfico transparente de telaraña comparando la solicitud acústica mental del Usuario frente al Match Matemático entregado.
- ⚡ **Desambiguador Cognitivo:** Motor "Burbuja" de Intercepción de Estados. Detecta cuando dos tracks/artistas compiten por el mismo string, mandando diccionarios de Payload al motor gráfico Vanilla-JS para crear Modales Asíncronos.
- 🎨 **Estética Glassmorphism Premium:** Interfaz de usuario "Zero Dependency" en CSS Responsivo (Mobile Ready), implementando filtros difuminados interactivos.

## 🛠️ Instalación y Uso (Local)

1. **Clona el ecosistema:**
    ```bash
    git clone https://github.com/TuUsuario/ai-music-recommender.git
    cd ai-music-recommender
    ```

2. **Descarga el Dataset Neuronal:**
    Deberás descargar el archivo [Spotify 1.2M+ Songs](https://www.kaggle.com/datasets/amitanshjoshi/spotify-1million-tracks) desde Kaggle. Posiciónalo dentro del directorio base: `/data/spotify_data.csv`.

3. **Instala Librerías Base:**
    ```bash
    pip install pandas numpy scikit-learn vaderSentiment deep-translator fastapi uvicorn
    ```

4. **Inicia el Servidor FastAPI:**
    ```bash
    python src/server.py
    ```
5. **Abre la App:** Dirígete a `http://localhost:8000` en tu navegador. 

## 🚀 Deploy de Producción (Vercel + Backend Python)

Para este proyecto, la arquitectura recomendada es:
- **Frontend estático** en Vercel (`public/`)
- **Backend FastAPI** en un servicio persistente (Render/Railway/Fly/VPS)

### 1) Backend (FastAPI)

1. Sube el repo al proveedor backend.
2. Configura comando de inicio:
   ```bash
   uvicorn src.server:app --host 0.0.0.0 --port $PORT
   ```
3. Configura variables de entorno usando `.env.example`.
4. Asegura que `SPOTIPY_REDIRECT_URI` apunte a:
   - `https://tu-backend.com/api/spotify/callback`
5. Carga el dataset en el backend (`data/spotify_data.csv`) o desde almacenamiento externo.

### 2) Frontend (Vercel)

1. Importa el repo en Vercel.
2. Framework preset: **Other**.
3. Build command: vacío.
4. Output directory: `public`.
5. Edita `public/config.js` para apuntar tu backend real:
   ```js
   window.APP_CONFIG = { API_BASE_URL: "https://tu-backend.com" };
   ```

### 3) Spotify OAuth (usuarios web)

- La web usa endpoints:
  - `GET /api/spotify/login`
  - `GET /api/spotify/callback`
  - `GET /api/spotify/status`
  - `POST /api/spotify/logout`
- Cada usuario conecta su cuenta y después puede exportar playlists desde la UI.
- Importación de playlists:
  - **públicas**: funciona sin login
  - **privadas**: requiere login Spotify del usuario

### 4) Restricción real de Spotify

Si tu app está en **Development mode** en Spotify Dashboard:
- solo los usuarios agregados en *User Management* podrán autenticar.

Para abrirlo a público general:
- solicita extensión de cuota/revisión de la app en Spotify Developer.

## 🗺️ Arquitectura de Carpetas
```
📁 recomendador-musica/
 ├── 📁 src/
 │    ├── recommender.py  # (Núcleo de Distancias Euclidianas / NLP)
 │    ├── server.py       # (Middle-Layer API Rest en Uvicorn)
 │    └── spotify_manager.py  # (Módulo OAuth Experimental)
 ├── 📁 public/
 │    ├── index.html      # (DOM & Canvas Charting)
 │    ├── style.css       # (Glassmorphism UI/UX)
 │    └── app.js          # (Manejador Híbrido Asíncrono / Modales)
 ├── 📁 data/             # (Requiere el CSV Maestro de Kaggle)
 └── README.md
```

---
Diseñado meticulosamente conectando Data Science puro y Diseño Web de Grado Consumo.

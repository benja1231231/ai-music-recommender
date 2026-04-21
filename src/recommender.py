from sklearn.metrics.pairwise import cosine_similarity
import logging
import os
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.preprocessing import StandardScaler # StandardScaler es mejor para Cosine Similarity con datos musicales
from sklearn.neighbors import NearestNeighbors
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from deep_translator import GoogleTranslator

# Configuración de Logging Profesional
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

try:
    from spotify_manager import SpotifyManager
except ImportError:
    SpotifyManager = None

class MusicRecommender:
    """
    Motor Híbrido Avanzado (Nivel Producción).
    Combina: NER dinámico, Búsqueda Vectorial Indexada, NLP y Spotify APIs.
    """
    
    def __init__(self):
        self.nlp = SentimentIntensityAnalyzer()
        self.translator = GoogleTranslator(source='es', target='en')
        self.scaler = StandardScaler() # Regresamos a StandardScaler para centrar los datos en 0
        self.nn_model = None 
        
        # Modelo de Embeddings Locales
        logger.info("Cargando modelo de lenguaje local (MiniLM)...")
        self.embedder = SentenceTransformer('paraphrase-MiniLM-L3-v2')
        
        # Dimensiones del ADN Acústico (Expandido para mayor precisión)
        self.caracteristicas = ['valence', 'energy', 'danceability', 'acousticness', 'instrumentalness', 'speechiness', 'tempo']
        self.df = None
        self.generos_conocidos = set()
        self.artistas_conocidos = set()
        
        # Conector Externo
        try:
            if SpotifyManager:
                self.spotify = SpotifyManager()
            else:
                self.spotify = None
        except Exception as e:
            logger.warning(f"No se pudo inicializar SpotifyManager: {e}")
            self.spotify = None

    def preparar_dataset(self, ruta_csv=None):
        logger.info("Inicializando el Motor de Inteligencia Artificial...")
        if ruta_csv and os.path.exists(ruta_csv):
            try:
                columnas_interes = [
                    'valence', 'energy', 'danceability', 'acousticness', 'popularity', 
                    'artist', 'track_name', 'track_genre', 'instrumentalness', 
                    'loudness', 'speechiness', 'tempo', 'liveness', 'track_id'
                ]
                
                self.df = pd.read_csv(
                    ruta_csv, 
                    usecols=lambda x: x in columnas_interes or x in ['artists', 'artist_name', 'genre'],
                    engine='c',
                    low_memory=True
                )
            except Exception as e:
                logger.error(f"Error al cargar dataset: {e}. Intentando carga simple.")
                self.df = pd.read_csv(ruta_csv)

            # Normalización de nombres de columnas
            rename_dict = {'artists': 'artist', 'artist_name': 'artist', 'genre': 'track_genre'}
            self.df.rename(columns={k: v for k, v in rename_dict.items() if k in self.df.columns}, inplace=True)
            
            # Limpieza de duplicados
            if 'track_name' in self.df.columns and 'artist' in self.df.columns:
                self.df = self.df.drop_duplicates(subset=['track_name', 'artist'])
                
            # Expandir dimensiones si están disponibles
            features_extra = ['instrumentalness', 'loudness', 'speechiness', 'tempo', 'liveness']
            for f in features_extra:
                if f in self.df.columns and f not in self.caracteristicas:
                    self.caracteristicas.append(f)
            
            # Tipos de datos eficientes
            for col in self.caracteristicas + ['popularity']:
                if col in self.df.columns:
                    self.df[col] = self.df[col].astype('float32')
                    
            columnas_necesarias = self.caracteristicas + ['artist', 'track_name']
            if 'track_genre' in self.df.columns:
                columnas_necesarias.append('track_genre')
                
            self.df = self.df.dropna(subset=columnas_necesarias)
            
            if 'popularity' not in self.df.columns:
                self.df['popularity'] = 50.0
            
            # Indexación para búsquedas rápidas
            logger.info("Indexando metadatos para búsqueda instantánea...")
            logger.info(f"Columnas cargadas: {list(self.df.columns)}")
            self.df['track_name_lower'] = self.df['track_name'].str.lower()
            self.df['artist_lower'] = self.df['artist'].str.lower()
            if 'track_genre' in self.df.columns:
                self.df['track_genre_lower'] = self.df['track_genre'].str.lower()
            
            # --- MEJORA SENIOR: Indexación Vectorial con Scikit-Learn ---
            logger.info("Construyendo índice vectorial para búsqueda musical...")
            
            # Asegurar que todas las características existen
            self.caracteristicas = [c for c in self.caracteristicas if c in self.df.columns]
            
            datos_estandarizados = self.scaler.fit_transform(self.df[self.caracteristicas])
            for i, caracteristica in enumerate(self.caracteristicas):
                self.df[f"{caracteristica}_scaled"] = datos_estandarizados[:, i].astype('float32')
            
            # Entrenar modelo de vecinos cercanos (Usamos cosine para el índice)
            self.nn_model = NearestNeighbors(n_neighbors=200, algorithm='auto', metric='cosine')
            self.nn_model.fit(datos_estandarizados)
            
            self.artistas_conocidos = set(self.df['artist'].str.lower().unique())
            if 'track_genre' in self.df.columns:
                self.generos_conocidos = set(self.df['track_genre'].dropna().str.lower().unique())
            
            logger.info(f"¡Éxito! {len(self.df):,} canciones cargadas e indexadas.")
        else:
            logger.warning("Dataset no encontrado o ruta inválida. Cargando modo prueba.")
            self._cargar_mock_dataset()

    def _cargar_mock_dataset(self):
        datos_mock = {
            'track_name': ['Bohemian Rhapsody', 'Levitating', 'Someone Like You', 'Danza Kuduro'],
            'artist': ['Queen', 'Dua Lipa', 'Adele', 'Don Omar'],
            'valence': [0.3, 0.9, 0.2, 0.8],
            'energy': [0.5, 0.8, 0.3, 0.9],
            'danceability': [0.4, 0.8, 0.4, 0.9],
            'acousticness': [0.1, 0.05, 0.9, 0.1],
            'popularity': [100, 95, 90, 85],
            'track_genre': ['rock', 'pop', 'pop', 'reggaeton']
        }
        self.df = pd.DataFrame(datos_mock)
        self.df['track_name_lower'] = self.df['track_name'].str.lower()
        self.df['artist_lower'] = self.df['artist'].str.lower()
        if 'track_genre' in self.df.columns:
            self.df['track_genre_lower'] = self.df['track_genre'].str.lower()
            
        datos_estandarizados = self.scaler.fit_transform(self.df[self.caracteristicas])
        for i, caracteristica in enumerate(self.caracteristicas):
            self.df[f"{caracteristica}_scaled"] = datos_estandarizados[:, i]
            
        self.nn_model = NearestNeighbors(n_neighbors=2, algorithm='auto', metric='euclidean')
        self.nn_model.fit(datos_estandarizados)
        logger.info("Dataset de prueba cargado correctamente.")

    def _imprimir_resultados(self, titulo, recomendaciones):
        print("\n" + "━"*75)
        print(f"  {titulo}  ".center(75, "✧"))
        print("━"*75)
        for idx, row in recomendaciones.iterrows():
            print(f"  🎧 {row['track_name']} - {row['artist']}")
            genero = row.get('track_genre', 'Desconocido').title()
            print(f"      ▶ Popularidad: {int(row['popularity'])} ⭐ | Género: {genero}")
        print("━"*75 + "\n")

    def _expandir_resultados_para_export(self, recomendaciones, cantidad_resultados, exportar):
        if not exportar or recomendaciones.empty or len(recomendaciones) >= cantidad_resultados:
            return recomendaciones
        faltantes = cantidad_resultados - len(recomendaciones)
        extra = recomendaciones.sample(n=faltantes, replace=True, random_state=42)
        return pd.concat([recomendaciones, extra], ignore_index=True)

    def recomendar(
        self,
        input_usuario,
        modo='contenido',
        exportar=False,
        override_type=None,
        override_index=None,
        spotify_token=None
    ):
        input_limpio = input_usuario.lower()
        cantidad_resultados = 15 if exportar else 6
        
        if modo == 'contenido':
            return self._recomendar_por_contenido(input_limpio, input_usuario, cantidad_resultados, override_type, override_index)
        elif modo == 'nlp':
            return self._recomendar_por_nlp(input_usuario, cantidad_resultados)
        elif modo == 'spotify_import':
            return self._recomendar_por_spotify(input_usuario, cantidad_resultados, spotify_token)
        
        return None

    def _recomendar_por_contenido(self, input_limpio, input_original, cantidad, override_type, override_index):
        match_artista = self.df['artist_lower'] == input_limpio
        match_cancion = self.df['track_name_lower'] == input_limpio
        
        if not match_artista.any() and not match_cancion.any():
            match_artista = self.df['artist_lower'].str.contains(input_limpio, case=False, na=False, regex=False)
            match_cancion = self.df['track_name_lower'].str.contains(input_limpio, case=False, na=False, regex=False)
            
        if not match_artista.any() and not match_cancion.any():
            logger.info(f"Sin match local para '{input_original}'. Buscando en Spotify...")
            if self.spotify:
                spotify_fallback = self.spotify.buscar_y_recomendar_por_query(input_original, limit=cantidad)
                if spotify_fallback:
                    return {"status": "success", "data": pd.DataFrame(spotify_fallback), "chart_data": {}, "source": "spotify_fallback"}
            return None

        # Desambiguación
        if match_artista.any() and match_cancion.any():
            if override_type == 'artista': match_cancion = pd.Series([False]*len(self.df), index=self.df.index)
            elif override_type == 'cancion' or override_index is not None: match_artista = pd.Series([False]*len(self.df), index=self.df.index)
            else: return {"status": "conflict", "type": "artist_vs_track", "message": f"Conflict: '{input_original}' is both Artist and Track."}

        if match_artista.any():
            logger.info(f"Analizando discografía del Artista: '{input_original}'")
            origen = self.df[match_artista]
            id_origen = set() # No hay ID único para un artista
        else:
            logger.info(f"Analizando Canción: '{input_original}'")
            origen = self.df[match_cancion]
            if len(origen) > 1 and override_index is None:
                opciones = origen.sort_values(by='popularity', ascending=False).head(10)
                return {"status": "conflict", "type": "multiple_tracks", "options": opciones[['track_name', 'artist', 'popularity']].to_dict(orient='records'), "message": f"Found multiple versions of '{input_original}'."}
            if override_index is not None: origen = origen.iloc[[override_index]]
            id_origen = set(origen.index)

        # --- MEJORA V10: PRECISIÓN MUSICAL AVANZADA ---
        columnas_scaled = [f"{col}_scaled" for col in self.caracteristicas]
        
        # Ponderación "Soul of Music" (Pesos para capturar el sentimiento real)
        pesos_dict = {
            'valence': 3.5,     # El sentimiento es lo más importante
            'energy': 3.0,      # La intensidad define el género
            'acousticness': 2.5, # Crítico para no mezclar acústico con electrónico
            'danceability': 2.0,
            'instrumentalness': 2.0,
            'tempo': 1.5,
            'speechiness': 1.0
        }
        pesos_vector = np.array([pesos_dict.get(c, 1.0) for c in self.caracteristicas])
        
        # Vector promedio de origen con pesos aplicados
        vector_origen = (origen[columnas_scaled].mean().values * pesos_vector).reshape(1, -1)
        
        # Búsqueda inicial por Vecinos Cercanos (usando la métrica Coseno ya configurada en el init)
        distancias, indices = self.nn_model.kneighbors(origen[columnas_scaled].mean().values.reshape(1, -1), n_neighbors=max(1000, cantidad * 50))
        df_candidatos = self.df.iloc[indices[0]].copy()
        
        # ELIMINAR ORIGEN INMEDIATAMENTE para evitar match 100% consigo mismo
        if match_artista.any():
            df_candidatos = df_candidatos[df_candidatos['artist_lower'] != input_limpio]
        else:
            df_candidatos = df_candidatos[~df_candidatos.index.isin(id_origen)]

        # Recalcular Similitud Coseno con Pesos Musicales
        matriz_candidatos = df_candidatos[columnas_scaled].values * pesos_vector
        similitudes = cosine_similarity(vector_origen, matriz_candidatos).flatten()
        df_candidatos['vibe_similarity'] = similitudes
        
        # --- FILTRO DE GÉNERO RIGUROSO ---
        generos_origen = set(origen['track_genre_lower'].dropna().unique())
        
        def calcular_match_honesto(row):
            # Similitud base (0 a 100)
            # Al usar StandardScaler, la similitud coseno es mucho más sensible
            sim = max(0.0, row['vibe_similarity'])
            
            # sim=0.8 -> match=~6% (exigente), sim=0.9 -> match=~28%, sim=0.95 -> match=54%, sim=0.98 -> match=83%
            base_match = (sim ** 12) * 100.0
            
            # Bono por género
            es_mismo_genero = any(g in str(row['track_genre_lower']) for g in generos_origen)
            
            if es_mismo_genero:
                return min(98.0, base_match + 10.0) if base_match > 50 else base_match + 5.0
            else:
                return min(75.0, base_match)

        df_candidatos['match_percent'] = df_candidatos.apply(calcular_match_honesto, axis=1)
        
        # Scoring Híbrido Rebalanceado (V14)
        # Vibe Similarity (60%) + Bonus Género (25%) + Popularidad (15%)
        genre_bonus = df_candidatos['track_genre_lower'].apply(lambda x: 0.3 if any(g in str(x) for g in generos_origen) else 0.0)
        df_candidatos['hybrid_score'] = (df_candidatos['vibe_similarity'] * 0.60) + (genre_bonus * 0.25) + ((df_candidatos['popularity']/100.0) * 0.15)
        
        recomendaciones = df_candidatos.sort_values(by='hybrid_score', ascending=False).head(cantidad)
        
        radar_cols = [c for c in ['valence', 'energy', 'danceability', 'acousticness', 'liveness'] if c in self.caracteristicas]
        return {
            "status": "success", "data": recomendaciones,
            "chart_data": {"target": origen[radar_cols].mean().to_dict(), "recommendations": recomendaciones[radar_cols].mean().to_dict()}
        }

    def _recomendar_por_nlp(self, input_usuario, cantidad):
        logger.info(f"Analizando intención semántica: '{input_usuario}'...")
        try:
            traduccion = self.translator.translate(input_usuario)
        except:
            traduccion = input_usuario
            
        texto_en = traduccion.lower() 
        texto_es = input_usuario.lower()
        string_compuesto = f" {texto_es} {texto_en} "
        
        # --- MEJORA V6: BÚSQUEDA SEMÁNTICA (OPCIÓN 3) ---
        # Mapeo de frases semánticas a vectores acústicos
        frases_clave = [
            "sad cry lonely depressed slow acoustic",
            "happy joy good vibes party energy dance",
            "workout gym power aggressive hard energy",
            "sleep relax chill soft peaceful calm",
            "focus study work concentration instrumental",
            "angry rage fury metal hard rock aggressive",
            "romantic love heart passion soft",
            "summer beach party tropical dance"
        ]
        
        embeddings_claves = self.embedder.encode(frases_clave)
        embedding_usuario = self.embedder.encode([traduccion])
        
        # Calcular similitud coseno (vía producto punto ya que están normalizados)
        similitudes = np.dot(embeddings_claves, embedding_usuario.T).flatten()
        indice_top = np.argmax(similitudes)
        top_score = similitudes[indice_top]
        
        # Atributos base
        valence_target, energy_target, dance_target, acoustic_target = 0.5, 0.5, 0.5, 0.5
        tempo_target = 110.0
        
        # Mapeo de la frase semántica más cercana
        vibe_targets = [
            {'valence': 0.1, 'energy': 0.2, 'acoustic': 0.8, 'tempo': 65}, # sad
            {'valence': 0.9, 'energy': 0.8, 'dance': 0.8, 'tempo': 125}, # happy
            {'valence': 0.6, 'energy': 0.95, 'dance': 0.5, 'tempo': 150}, # workout
            {'valence': 0.5, 'energy': 0.1, 'acoustic': 0.9, 'tempo': 60}, # sleep
            {'valence': 0.5, 'energy': 0.3, 'acoustic': 0.6, 'tempo': 85}, # focus
            {'valence': 0.2, 'energy': 0.95, 'acoustic': 0.1, 'tempo': 160}, # angry
            {'valence': 0.8, 'energy': 0.4, 'acoustic': 0.6, 'tempo': 80}, # romantic
            {'valence': 0.8, 'energy': 0.7, 'dance': 0.9, 'tempo': 120}  # summer
        ]
        
        if top_score > 0.4:
            logger.info(f"Vibe semántica detectada: '{frases_clave[indice_top]}' (Score: {top_score:.2f})")
            targets = vibe_targets[indice_top]
            if 'valence' in targets: valence_target = targets['valence']
            if 'energy' in targets: energy_target = targets['energy']
            if 'dance' in targets: dance_target = targets['dance']
            if 'acoustic' in targets: acoustic_target = targets['acoustic']
            if 'tempo' in targets: tempo_target = targets['tempo']

        # Detección de sentimientos (Mood) - Refinamiento final
        sentimiento = self.nlp.polarity_scores(traduccion)
        if abs(sentimiento['compound']) > 0.3:
            valence_target = (sentimiento['compound'] + 1.0) / 2.0
            logger.info(f"Ajuste por sentimiento: {sentimiento['compound']} -> Valence: {valence_target:.2f}")

        # Detección de entidades (Artistas/Géneros)
        artistas_detectados = [art for art in self.artistas_conocidos if len(art) > 3 and f" {art} " in string_compuesto]
        generos_detectados = [gen for gen in self.generos_conocidos if f" {gen} " in string_compuesto]
        
        # Crear vector target mental
        dict_mental = {'valence': [valence_target], 'energy': [energy_target], 'danceability': [dance_target], 'acousticness': [acoustic_target]}
        if 'tempo' in self.caracteristicas: dict_mental['tempo'] = [tempo_target]
        
        cancion_mental = pd.DataFrame(dict_mental)
        for col in self.caracteristicas:
            if col not in cancion_mental.columns:
                cancion_mental[col] = self.df[col].mean()
        
        # Búsqueda Vectorial Ponderada
        columnas_scaled = [f"{col}_scaled" for col in self.caracteristicas]
        pesos_dict = {'valence': 4.0, 'energy': 3.0, 'danceability': 2.0, 'tempo': 1.5, 'acousticness': 2.0}
        pesos_vector = np.array([pesos_dict.get(c, 1.0) for c in self.caracteristicas])
        
        vector_target = (self.scaler.transform(cancion_mental[self.caracteristicas])[0] * pesos_vector).reshape(1, -1)
        
        # Búsqueda inicial
        distancias, indices = self.nn_model.kneighbors(self.scaler.transform(cancion_mental[self.caracteristicas])[0].reshape(1, -1), n_neighbors=max(500, cantidad * 20))
        df_res = self.df.iloc[indices[0]].copy()
        
        # Similitud Coseno Ponderada
        matriz_ponderada = df_res[columnas_scaled].values * pesos_vector
        similitudes = cosine_similarity(vector_target, matriz_ponderada).flatten()
        df_res['vibe_similarity'] = similitudes
        
        # Bonus por género o artistas detectados
        df_res['bonus_score'] = 1.0
        if generos_detectados:
            df_res['bonus_score'] += df_res['track_genre_lower'].apply(lambda x: 0.5 if any(g in str(x) for g in generos_detectados) else 0.0)
        if artistas_detectados:
            df_res['bonus_score'] += df_res['artist_lower'].apply(lambda x: 0.5 if any(a in str(x) for a in artistas_detectados) else 0.0)

        # Match Percent Honesto para NLP
        sim_nlp = max(0.0, df_res['vibe_similarity'])
        df_res['match_percent'] = (sim_nlp ** 10) * 100.0
        
        # Hybrid Score Rebalanceado (Vibe Similarity 60% + Bonus 25% + Pop 15%)
        df_res['hybrid_score'] = (df_res['vibe_similarity'] * 0.60) + ((df_res['bonus_score']-1.0) * 0.50) + ((df_res['popularity']/100.0) * 0.15)
        
        recomendaciones = df_res.sort_values(by='hybrid_score', ascending=False).head(cantidad)
        
        radar_cols = [c for c in ['valence', 'energy', 'danceability', 'acousticness', 'liveness'] if c in self.caracteristicas]
        return {
            "status": "success", "data": recomendaciones,
            "chart_data": {"target": cancion_mental[radar_cols].iloc[0].to_dict(), "recommendations": recomendaciones[radar_cols].mean().to_dict()}
        }

    def _recomendar_por_spotify(self, playlist_id, cantidad, token):
        if not self.spotify: return {"status": "error", "message": "Spotify no configurado."}
        res = self.spotify.extraer_tracks_de_playlist(playlist_id, token_info=token)
        tracks = res.get("tracks")
        if not tracks: return {"status": "error", "message": "No se pudieron obtener canciones."}
        
        df_pl = pd.DataFrame(tracks)
        filtro = self.df['track_name_lower'].isin(df_pl['track_name'].str.lower()) | self.df['artist_lower'].isin(df_pl['artist'].str.lower())
        df_match = self.df[filtro]
        
        if df_match.empty: return {"status": "error", "message": "No hay coincidencias en la base de datos local."}
        
        vector_origen = df_match[[f"{c}_scaled" for c in self.caracteristicas]].mean().values.reshape(1, -1)
        distancias, indices = self.nn_model.kneighbors(vector_origen, n_neighbors=max(200, cantidad * 10))
        
        df_res = self.df.iloc[indices[0]].copy()
        df_res = df_res[~df_res.index.isin(df_match.index)] # No recomendar lo que ya está en la playlist
        df_res['distancia'] = distancias[0][:len(df_res)]
        
        df_res['match_percent'] = df_res['distancia'].apply(lambda d: min(100.0, max(1.0, 100.0 - (d * 15.0))))
        df_res['hybrid_score'] = (df_res['match_percent'] * 0.85) + (df_res['popularity'] * 0.15)
        
        recomendaciones = df_res.sort_values(by='hybrid_score', ascending=False).head(cantidad)
        radar_cols = [c for c in ['valence', 'energy', 'danceability', 'acousticness', 'liveness'] if c in self.caracteristicas]
        return {
            "status": "success", "data": recomendaciones,
            "chart_data": {"target": df_match[radar_cols].mean().to_dict(), "recommendations": recomendaciones[radar_cols].mean().to_dict()}
        }

if __name__ == "__main__":
    # Mantener compatibilidad con ejecución CLI
    motor = MusicRecommender()
    motor.preparar_dataset('data/spotify_data.csv')
    # ... resto del código CLI ...

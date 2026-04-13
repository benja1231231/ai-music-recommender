import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from scipy.spatial.distance import euclidean
from deep_translator import GoogleTranslator
import os
try:
    from spotify_manager import SpotifyManager
except ImportError:
    SpotifyManager = None

class MusicRecommender:
    """
    Motor Híbrido Avanzado (Nivel Producción).
    Combina: NER dinámico, Geometría Espacial, NLP y Spotify APIs.
    """
    
    def __init__(self):
        self.nlp = SentimentIntensityAnalyzer()
        self.translator = GoogleTranslator(source='es', target='en')
        self.scaler = StandardScaler()
        # El motor K-Means y FAISS fue removido porque la vectorización pura de Numpy resolvió los cálculos 9D a velocidad L1 Cache para 1.2M iteraciones
        self.caracteristicas = ['valence', 'energy', 'danceability', 'acousticness']
        self.df = None
        self.generos_conocidos = set()
        self.artistas_conocidos = set()
        
        # Conector Externo (Habilitado para uso Local)
        try:
            if SpotifyManager:
                self.spotify = SpotifyManager()
            else:
                self.spotify = None
        except:
            self.spotify = None
    def preparar_dataset(self, ruta_csv=None):
        print("\n[INFO] Inicializando el Motor de Inteligencia Artificial...")
        if ruta_csv:
            # Restaurado: Carga completa (1.2M+ canciones)
            try:
                columnas_interes = ['valence', 'energy', 'danceability', 'acousticness', 'popularity', 'artist', 'track_name', 'track_genre', 'instrumentalness', 'loudness', 'speechiness', 'tempo', 'liveness']
                
                self.df = pd.read_csv(
                    ruta_csv, 
                    usecols=lambda x: x in columnas_interes or x in ['artists', 'artist_name', 'genre'],
                    engine='c',
                    low_memory=True
                )
            except Exception as e:
                print(f"[ERROR] Al cargar dataset: {e}. Intentando carga simple.")
                self.df = pd.read_csv(ruta_csv)

            if 'artists' in self.df.columns:
                self.df.rename(columns={'artists': 'artist'}, inplace=True)
            if 'artist_name' in self.df.columns:
                self.df.rename(columns={'artist_name': 'artist'}, inplace=True)
            if 'genre' in self.df.columns:
                self.df.rename(columns={'genre': 'track_genre'}, inplace=True)
            
            # Limpieza rápida
            if 'track_name' in self.df.columns and 'artist' in self.df.columns:
                self.df = self.df.drop_duplicates(subset=['track_name', 'artist'])
                
            features_extra = ['instrumentalness', 'loudness', 'speechiness', 'tempo', 'liveness']
            for f in features_extra:
                if f in self.df.columns:
                    if f not in self.caracteristicas:
                        self.caracteristicas.append(f)
            
            # Tipos de datos eficientes para manejar 1.2M sin lag
            for col in self.caracteristicas + ['popularity']:
                if col in self.df.columns:
                    self.df[col] = self.df[col].astype('float32')
                    
            columnas_necesarias = self.caracteristicas + ['artist', 'track_name']
            if 'track_genre' in self.df.columns:
                columnas_necesarias.append('track_genre')
                
            self.df = self.df.dropna(subset=columnas_necesarias)
            
            if 'popularity' not in self.df.columns:
                self.df['popularity'] = 50.0
            
            # Optimización para búsquedas rápidas (1.2M rows)
            print("   [INFO] Indexando nombres para búsqueda instantánea...")
            self.df['track_name_lower'] = self.df['track_name'].str.lower()
            self.df['artist_lower'] = self.df['artist'].str.lower()
            if 'track_genre' in self.df.columns:
                self.df['track_genre_lower'] = self.df['track_genre'].str.lower()
            
            print(f"[SUCCESS] Cargadas {len(self.df):,} canciones! Motor listo con el dataset completo.")
        else:
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
            print("[SUCCESS] Dataset de prueba cargado (Práctica).")
        
        datos_estandarizados = self.scaler.fit_transform(self.df[self.caracteristicas])
        for i, caracteristica in enumerate(self.caracteristicas):
            self.df[f"{caracteristica}_scaled"] = datos_estandarizados[:, i]
        
        self.artistas_conocidos = set(self.df['artist'].str.lower().unique())
        if 'track_genre' in self.df.columns:
            self.generos_conocidos = set(self.df['track_genre'].dropna().str.lower().unique())
            
        print("[SUCCESS] Caché de Identidades Rápidas (NER) ensamblada en Memoria.\n")
    def _imprimir_resultados(self, titulo, recomendaciones):
        print("\n" + "━"*75)
        print(f"  {titulo}  ".center(75, "✧"))
        print("━"*75)
        for idx, row in recomendaciones.iterrows():
            print(f"  🎧 {row['track_name']} - {row['artist']}")
            genero = row.get('track_genre', 'Desconocido').title()
            print(f"      ▶ Popularidad: {int(row['popularity'])} ⭐ | Género: {genero}")
        print("━"*75 + "\n")
    def recomendar(self, input_usuario, modo='contenido', exportar=False, override_type=None, override_index=None):
        input_limpio = input_usuario.lower()
        cantidad_resultados = 15 if exportar else 6
        
        if modo == 'contenido':
            match_artista = self.df['artist_lower'] == input_limpio
            match_cancion = self.df['track_name_lower'] == input_limpio
            
            if not match_artista.any() and not match_cancion.any():
                match_artista = self.df['artist_lower'].str.contains(input_limpio, case=False, na=False, regex=False)
                match_cancion = self.df['track_name_lower'].str.contains(input_limpio, case=False, na=False, regex=False)
            if not match_artista.any() and not match_cancion.any():
                print(f"\n   ❌ Lo siento, no pudimos encontrar ningún artista ni canción llamado '{input_usuario}'.")
                return None
            if match_artista.any() and match_cancion.any():
                if override_type == 'artista':
                    match_cancion = pd.Series([False]*len(self.df), index=self.df.index)
                elif override_type == 'cancion' or override_index is not None:
                    match_artista = pd.Series([False]*len(self.df), index=self.df.index)
                else:
                    return {
                        "status": "conflict",
                        "type": "artist_vs_track",
                        "message": f"Hemos detectado a un Artista y una Canción que se llaman '{input_usuario}'. ¿Cuál buscas?"
                    }
            if match_artista.any():
                print(f"[INFO] Artista Encontrado! Analizando la discografia de: '{input_usuario}'...")
                canciones_origen = self.df[match_artista]
                df_resultados = self.df[~match_artista].copy()
            else:
                print(f"[INFO] Cancion Encontrada! Analizando el track...")
                canciones_origen = self.df[match_cancion]
                
                canciones_origen = canciones_origen.sort_values(by='popularity', ascending=False).reset_index(drop=True)
                
                if len(canciones_origen) > 1:
                    if override_index is not None:
                        canciones_origen = canciones_origen.iloc[[override_index]]
                    else:
                        opciones = canciones_origen.head(10)
                        lista_opcn = opciones[['track_name', 'artist', 'popularity']].to_dict(orient='records')
                        return {
                            "status": "conflict",
                            "type": "multiple_tracks",
                            "options": lista_opcn,
                            "message": f"Encontramos {len(canciones_origen)} versiones distintas tituladas '{input_usuario}'. Selecciona la correcta:"
                        }
                    
                df_resultados = self.df[~match_cancion].copy()
                
            columnas_scaled = [f"{col}_scaled" for col in self.caracteristicas]
            vector_origen = canciones_origen[columnas_scaled].mean().values
            
            if 'track_genre' in self.df.columns:
                generos_artista = canciones_origen['track_genre_lower'].dropna().unique()
                if len(generos_artista) > 0:
                    print(f"   [INFO] Mismo ADN detectado en Generos: {', '.join(generos_artista)[:50]}... Filtrando ruidos.")
                    df_resultados = df_resultados[df_resultados['track_genre_lower'].isin(generos_artista)]
            
            # CÁLCULO VECTORIAL HYPER-RÁPIDO
            matriz_canciones = df_resultados[columnas_scaled].values
            distancias = np.linalg.norm(matriz_canciones - vector_origen, axis=1)
            df_resultados['distancia'] = distancias
            
            # CÁLCULO HÍBRIDO: 85% ADN Acústico / 15% Fama Global
            df_resultados['match_percent'] = df_resultados['distancia'].apply(
                lambda d: min(100.0, max(1.0, 100.0 - (d * 12.0)))
            )
            df_resultados['hybrid_score'] = (df_resultados['match_percent'] * 0.85) + (df_resultados['popularity'] * 0.15)
            
            recomendaciones = df_resultados.sort_values(by='hybrid_score', ascending=False).head(cantidad_resultados).copy()
            
            self._imprimir_resultados(f"BÚSQUEDA EXTRACCIÓN GÉNERO ({cantidad_resultados} tracks)", recomendaciones)
            
            radar_cols = [c for c in ['valence', 'energy', 'danceability', 'acousticness', 'liveness'] if c in self.caracteristicas]
            dna_target = canciones_origen[radar_cols].mean().to_dict()
            dna_recs = recomendaciones[radar_cols].mean().to_dict()
            
            return {
                "status": "success",
                "data": recomendaciones,
                "chart_data": {"target": dna_target, "recommendations": dna_recs}
            }
            
        elif modo == 'nlp':
            print(f"[INFO] Analizando matriz psicologica y acustica de: '{input_usuario}'...")
            try:
                traduccion = self.translator.translate(input_usuario)
            except:
                traduccion = input_usuario
                
            texto_en = traduccion.lower() 
            texto_es = input_usuario.lower()
            string_compuesto = f" {texto_es} {texto_en} "
            
            palabras_es = set(texto_es.replace(',', ' ').replace('.', ' ').split())
            palabras_en = set(texto_en.replace(',', ' ').replace('.', ' ').split())
            todas_palabras = palabras_es.union(palabras_en)
            
            artistas_detectados = [art for art in self.artistas_conocidos if len(art) > 2 and f" {art} " in string_compuesto]
            generos_detectados = self.generos_conocidos.intersection(todas_palabras)
            
            if artistas_detectados or generos_detectados:
                print(f"   [INFO] Entidades Detectadas:")
                if generos_detectados: print(f"       ▶ Generos: {', '.join(generos_detectados).title()}")
                if artistas_detectados: print(f"       ▶ Influencias: {', '.join(artistas_detectados).title()}")
            sentimiento = self.nlp.polarity_scores(traduccion)
            valence = (sentimiento['compound'] + 1.0) / 2.0
            
            columnas_scaled = [f"{col}_scaled" for col in self.caracteristicas]
            df_resultados = self.df.copy()
            pesos_dimensionales = np.ones(len(self.caracteristicas))
            
            if artistas_detectados:
                filtro_artistas = df_resultados['artist'].str.lower().isin(artistas_detectados)
                discografia_inspiradora = df_resultados[filtro_artistas]
                vector_origen = discografia_inspiradora[columnas_scaled].mean().values
                df_resultados = df_resultados[~filtro_artistas]
            else:
                energy_e, dance_e, acoustic_e = 0.5, 0.5, 0.5
                inst_e, speech_e, tempo_e, loud_e = None, None, None, None
                
                if any(p in string_compuesto for p in ['gym', 'workout', 'fit', 'entrenar']):
                    energy_e, dance_e, tempo_e, loud_e = 0.9, 0.8, 160.0, -3.0
                if any(p in string_compuesto for p in ['party', 'dance', 'fiesta', 'bailar']):
                    energy_e, dance_e, tempo_e = 0.85, 0.95, 125.0
                if any(p in string_compuesto for p in ['sleep', 'relax', 'chill', 'dormir', 'calma']):
                    energy_e, dance_e, acoustic_e, tempo_e, loud_e = 0.1, 0.2, 0.95, 70.0, -20.0
                if any(p in string_compuesto for p in ['sad', 'cry', 'triste', 'llorar', 'depresión']):
                    energy_e, acoustic_e = 0.2, 0.85
                    
                if any(p in string_compuesto for p in ['instrumental', 'sin voz', 'pista']):
                    inst_e, speech_e = 0.9, 0.0
                if any(p in string_compuesto for p in ['rap', 'cantar', 'voz', 'letra']):
                    speech_e, inst_e = 0.8, 0.0
                if any(p in string_compuesto for p in ['fast', 'rápido', 'acelerado']):
                    tempo_e = 170.0
                if any(p in string_compuesto for p in ['slow', 'lento', 'suave', 'despacio']):
                    tempo_e = 65.0
                
                dict_mental = {'valence': [valence], 'energy': [energy_e], 'danceability': [dance_e], 'acousticness': [acoustic_e]}
                if inst_e is not None and 'instrumentalness' in self.caracteristicas: dict_mental['instrumentalness'] = [inst_e]
                if speech_e is not None and 'speechiness' in self.caracteristicas: dict_mental['speechiness'] = [speech_e]
                if tempo_e is not None and 'tempo' in self.caracteristicas: dict_mental['tempo'] = [tempo_e]
                if loud_e is not None and 'loudness' in self.caracteristicas: dict_mental['loudness'] = [loud_e]
                
                cancion_mental = pd.DataFrame(dict_mental)
                for col in self.caracteristicas:
                    if col not in cancion_mental.columns:
                        cancion_mental[col] = self.df[col].mean()
                        
                cancion_mental = cancion_mental[self.caracteristicas] 
                vector_origen = self.scaler.transform(cancion_mental)[0]
                
                idx_valence = self.caracteristicas.index('valence')
                if valence > 0.8 or valence < 0.2:
                    pesos_dimensionales[idx_valence] = 3.0
                else:
                    pesos_dimensionales[idx_valence] = 1.5 
                
            if generos_detectados:
                df_resultados = df_resultados[df_resultados['track_genre'].str.lower().isin(generos_detectados)]
                if df_resultados.empty:
                    df_resultados = self.df.copy()
            
            matriz_canciones = df_resultados[columnas_scaled].values
            vector_ponderado = vector_origen * pesos_dimensionales
            matriz_ponderada = matriz_canciones * pesos_dimensionales
            
            distancias = np.linalg.norm(matriz_ponderada - vector_ponderado, axis=1)
            df_resultados['distancia'] = distancias
            
            # CÁLCULO HÍBRIDO: 85% ADN Acústico / 15% Fama Global
            df_resultados['match_percent'] = df_resultados['distancia'].apply(
                lambda d: min(100.0, max(1.0, 100.0 - (d * 12.0)))
            )
            df_resultados['hybrid_score'] = (df_resultados['match_percent'] * 0.85) + (df_resultados['popularity'] * 0.15)
            
            recomendaciones = df_resultados.sort_values(by='hybrid_score', ascending=False).head(cantidad_resultados).copy()
            
            self._imprimir_resultados(f"PRECISIÓN PSICOLÓGICA ({cantidad_resultados} tracks)", recomendaciones)
            
            radar_cols = [c for c in ['valence', 'energy', 'danceability', 'acousticness', 'liveness'] if c in self.caracteristicas]
            if artistas_detectados:
                dna_target = discografia_inspiradora[radar_cols].mean().to_dict()
            else:
                dna_target = cancion_mental[radar_cols].iloc[0].to_dict()
            dna_recs = recomendaciones[radar_cols].mean().to_dict()
            
            return {
                "status": "success",
                "data": recomendaciones,
                "chart_data": {"target": dna_target, "recommendations": dna_recs}
            }
        
        elif modo == 'spotify_import':
            if not self.spotify:
                return {"status": "error", "message": "Spotify no configurado localmente."}
                
            lista_canciones = self.spotify.extraer_tracks_de_playlist(input_usuario)
            if not lista_canciones:
                return {"status": "error", "message": "No se pudo extraer canciones de la playlist. Verifica que sea publica."}
                
            print(f"   [INFO] Cruzando {len(lista_canciones)} pistas con nuestra Base de Datos Kaggle para clonar su ADN...")
            
            df_playlist = pd.DataFrame(lista_canciones)
            nombres_buscados = df_playlist['track_name'].str.lower().tolist()
            artistas_buscados = df_playlist['artist'].str.lower().tolist()
            
            # Match heurístico: track coincidente o artista coincidente (USANDO COLUMNAS INDEXADAS)
            filtro_local = self.df['track_name_lower'].isin(nombres_buscados) | self.df['artist_lower'].isin(artistas_buscados)
            df_match = self.df[filtro_local]
            
            if df_match.empty:
               return {"status": "error", "message": "Ningun artista de tu playlist coincide con nuestra base de datos de 1.2M. Intenta con otra lista."}
               
            print(f"   [INFO] Genetica Acustica equivalente extraida via {len(df_match)} canciones locales compatibles!")
            
            columnas_scaled = [f"{col}_scaled" for col in self.caracteristicas]
            vector_origen = df_match[columnas_scaled].mean().values
            
            df_resultados = self.df.copy()
            # Ignoramos a los propios artistas mapeados para sugerir cosas NUEVAS
            df_resultados = df_resultados[~filtro_local]
            
            matriz_canciones = df_resultados[columnas_scaled].values
            distancias = np.linalg.norm(matriz_canciones - vector_origen, axis=1)
            df_resultados['distancia'] = distancias
            
            # CÁLCULO HÍBRIDO: Priorizamos cercanía genética
            df_resultados['match_percent'] = df_resultados['distancia'].apply(
                lambda d: min(100.0, max(1.0, 100.0 - (d * 15.0))) # Factor de castigo mayor para mas precision
            )
            # 85% ADN / 15% Popularidad para ser mas "fiel" a la playlist origen
            df_resultados['hybrid_score'] = (df_resultados['match_percent'] * 0.85) + (df_resultados['popularity'] * 0.15)
            
            recomendaciones = df_resultados.sort_values(by='hybrid_score', ascending=False).head(cantidad_resultados).copy()
            
            self._imprimir_resultados(f"CLONACIÓN DE PLAYLIST SPOTIFY ({cantidad_resultados} tracks)", recomendaciones)
            
            radar_cols = [c for c in ['valence', 'energy', 'danceability', 'acousticness', 'liveness'] if c in self.caracteristicas]
            dna_target = df_match[radar_cols].mean().to_dict()
            dna_recs = recomendaciones[radar_cols].mean().to_dict()
            
            return {
                "status": "success",
                "data": recomendaciones,
                "chart_data": {"target": dna_target, "recommendations": dna_recs}
            }
if __name__ == "__main__":
    import os
    os.system('cls' if os.name == 'nt' else 'clear') 
    
    try:
        motor = MusicRecommender()
        motor.preparar_dataset('data/dataset.csv')
    except Exception as e:
        print(f"Error Iniciando Motor: {e}")
        exit()
    
    while True:
        print("\n" + "═"*75)
        print("   🎧   SISTEMA AVANZADO DE RECOMENDACIÓN MUSICAL   🎧   ")
        print("═"*75)
        print("  [1] Búsqueda por Artista o Canción")
        print("  [2] Búsqueda por Mood (Sentimientos y Vibras)")
        print("  [3] Cerrar programa")
        print("─"*75)
        
        eleccion_menu = input("\n👉 Elige una opción del menú (1-3): ").strip()
        
        if eleccion_menu == '3':
            print("\n🎼 ¡Hasta pronto, que tengas buen día!\n")
            break
        elif eleccion_menu == '1':
            query = input("🎸 Escribe el nombre del Artista o Canción: ")
            motor.recomendar(query, modo='contenido', exportar=False)
        elif eleccion_menu == '2':
            query = input("🧠 Cuenta cómo te sientes (Ej: 'quiero música de rock feliz'): ")
            motor.recomendar(query, modo='nlp', exportar=False)
        else:
            print("❌ Opción inválida. Intenta nuevamente.")
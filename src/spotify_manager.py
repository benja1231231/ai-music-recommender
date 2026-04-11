import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os
import webbrowser
import pandas as pd
from dotenv import load_dotenv

class SpotifyManager:
    """
    Controlador de API de Spotify. 
    Se encarga de la exportación de tracks e importación de vectores ADN desde cuentas de usuarios.
    """
    def __init__(self):
        # Asegurar lectura del .env en el directorio raíz absoluto
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        env_path = os.path.join(root_dir, '.env')
        load_dotenv(dotenv_path=env_path)
        
        scope = "playlist-modify-public playlist-modify-private playlist-read-private"
        
        try:
            self.sp = spotipy.Spotify(auth_manager=SpotifyOAuth(scope=scope))
            self.user_id = self.sp.current_user()['id']
            print("   ✅ Conectado a la API de Spotify exitosamente.")
        except Exception as e:
            print("\n❌ Error Crítico: No se pudo conectar a Spotify.")
            print("[!] Verifica que tu archivo .env tenga el Client ID, Secret y la Redirect URI idéntica a tu Dashboard.")
            print("Detalle técnico:", e)
            self.user_id = None

    def exportar_recomendaciones_a_playlist(self, nombre_playlist, dataframe_resultados):
        if not self.user_id:
            print("\n❌ Servicio de Spotify no disponible. Verifica tus credenciales.")
            return

        print(f"\n🌐 Contactando satélites de Spotify para construir: '{nombre_playlist}'...")
        
        try:
            playlist = self.sp.user_playlist_create(self.user_id, nombre_playlist, public=True, description="Generado automáticamente por Motor AI Híbrido.")
            
            track_uris = []
            print("   [!] Traduciendo nombres de Kaggle a URIs de Spotify (esto puede tomar unos segundos)...")
            
            for _, row in dataframe_resultados.iterrows():
                # Búsqueda rigurosa
                query = f"track:{row['track_name']} artist:{row['artist']}"
                result = self.sp.search(q=query, type='track', limit=1)
                
                if result['tracks']['items']:
                    track_uris.append(result['tracks']['items'][0]['uri'])
                else:
                    # Búsqueda suave (A veces en Kaggle aparecen artistas múltiples con ; que en Spotify se escriben distinto)
                    query_suave = str(row['track_name'])
                    result_suave = self.sp.search(q=query_suave, type='track', limit=1)
                    if result_suave['tracks']['items']:
                        track_uris.append(result_suave['tracks']['items'][0]['uri'])
                        
            if track_uris:
                self.sp.playlist_add_items(playlist['id'], track_uris)
                url_lista = playlist['external_urls']['spotify']
                print(f"\n✨ ¡ÉXITO! Playlist creada en tu cuenta con {len(track_uris)} hermosas canciones.")
                print(f"👉 Enlace: {url_lista}")
                # Abre el navegador automáticamente (Magia UX)
                webbrowser.open(url_lista)
            else:
                print("\n❌ No se encontraron coincidencias exactas en la base de Spotify para esos tracks.")
                self.sp.user_playlist_unfollow(self.user_id, playlist['id']) # Borra la lista si quedó vacía
                
        except Exception as e:
            print(f"\n❌ Error al exportar: {e}")

    def extraer_tracks_de_playlist(self, playlist_url):
        if not self.user_id:
            print("\n❌ Servicio de Spotify no disponible. Verifica tus credenciales.")
            return None

        print("\n🌐 Analizando metadatos públicos de la lista desde Servidores de Spotify...")
        try:
            playlist_id = playlist_url.split('/')[-1].split('?')[0] 
            
            resultados = self.sp.playlist_tracks(playlist_id)
            lista_nombres = []
            tracks = resultados['items']
            
            # Paginación para listas largas
            while resultados['next'] and len(lista_nombres) < 300:
                resultados = self.sp.next(resultados)
                tracks.extend(resultados['items'])
                
            for item in tracks:
                if item.get('track') and item['track'].get('name'):
                    nombre_track = item['track']['name']
                    nombre_artist = item['track']['artists'][0]['name'] if item['track'].get('artists') else ""
                    lista_nombres.append({'track_name': nombre_track, 'artist': nombre_artist})
                    
            if not lista_nombres:
                print("   ❌ La lista de reproducción está vacía o el link es inválido.")
                return None
            
            # NOTA DE SEGURIDAD: Ya no pedimos sp.audio_features() porque Spotify revoca o bloquea 
            # esos endpoints avanzados a cuentas gratuitas o les tira errores 'Forbidden'.
            # Ahora devolveremos los nombres limpios y calcularemos la genética acústica de manera LOCAL.
            
            return lista_nombres
            
        except Exception as e:
            print("❌ Error extrayendo Playlist. Asegúrate que el link sea público y no sea exclusivo Premium.")
            print(f"Detalle Técnico: {e}")
            return None

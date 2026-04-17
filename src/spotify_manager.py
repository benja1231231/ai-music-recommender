import os
from typing import Optional

import pandas as pd
import spotipy
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyClientCredentials, SpotifyOAuth

class SpotifyManager:
    """
    Controlador de API de Spotify. 
    Se encarga de la exportación de tracks e importación de vectores ADN desde cuentas de usuarios.
    """
    def __init__(self):
        self.user_id = None
        self.sp = None
        # Asegurar lectura del .env en el directorio raíz absoluto
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        env_path = os.path.join(root_dir, '.env')
        
        if os.path.exists(env_path):
            load_dotenv(dotenv_path=env_path)
            print(f"   [INFO] Archivo .env cargado desde: {env_path}")
        else:
            print(f"   [WARN] Advertencia: No se encontro el archivo .env en {env_path}")

        client_id = os.getenv("SPOTIPY_CLIENT_ID")
        client_secret = os.getenv("SPOTIPY_CLIENT_SECRET")
        redirect_uri = os.getenv("SPOTIPY_REDIRECT_URI")

        if not all([client_id, client_secret, redirect_uri]):
            print("\n[ERROR] Faltan variables de entorno en el archivo .env")
            print(f"   IDs encontrados: ID={'OK' if client_id else 'Falta'}, Secret={'OK' if client_secret else 'Falta'}, URI={'OK' if redirect_uri else 'Falta'}")
            self.user_id = None
            return

        self.oauth_scope = (
            "playlist-modify-public playlist-modify-private "
            "playlist-read-private user-read-private user-read-email"
        )
        self.oauth = SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scope=self.oauth_scope,
            open_browser=True,
            cache_path=".cache",
            show_dialog=True
        )
        self.client_credentials = SpotifyClientCredentials(
            client_id=client_id,
            client_secret=client_secret
        )
        try:
            # Modo local/autónomo: intenta autenticar al iniciar con cache OAuth.
            self.sp = spotipy.Spotify(auth_manager=self.oauth)
            user_info = self.sp.current_user()
            if user_info:
                self.user_id = user_info.get("id")
                print(f"   [OK] Conectado a Spotify como: {user_info.get('display_name', self.user_id)}")
            else:
                print("   [WARN] Spotify inicializado pero sin usuario detectado.")
        except Exception as e:
            print(f"   [WARN] Spotify web/local no autenticado al inicio: {e}")

        print("   [OK] SpotifyManager inicializado.")

    def get_authorize_url(self, state: Optional[str] = None):
        return self.oauth.get_authorize_url(state=state)

    def exchange_code(self, code: str):
        token_info = self.oauth.get_access_token(code, as_dict=True, check_cache=False)
        return token_info

    def _refresh_if_needed(self, token_info: Optional[dict]):
        if not token_info:
            return None
        if self.oauth.is_token_expired(token_info):
            token_info = self.oauth.refresh_access_token(token_info["refresh_token"])
        return token_info

    def get_user_client(self, token_info: dict):
        token_info = self._refresh_if_needed(token_info)
        if not token_info:
            return None, None
        sp = spotipy.Spotify(auth=token_info["access_token"])
        return sp, token_info

    def get_public_client(self):
        return spotipy.Spotify(client_credentials_manager=self.client_credentials)

    def get_current_user(self, token_info: dict):
        sp, token_info = self.get_user_client(token_info)
        if not sp:
            return None, None
        return sp.current_user(), token_info

    def exportar_recomendaciones_a_playlist(self, nombre_playlist, dataframe_resultados, token_info: Optional[dict] = None):
        sp = None
        if token_info:
            sp, token_info = self.get_user_client(token_info)
        elif self.sp:
            sp = self.sp
        if not sp:
            return {
                "status": "error",
                "message": "Spotify no autenticado. Revisa .env y completa autorización local al iniciar.",
                "token_info": token_info
            }

        if "http" in nombre_playlist:
            nombre_playlist = "AI Recs: Playlist Importada"

        try:
            user_data = sp.current_user()
            if not user_data:
                raise Exception("No se pudo obtener la información del usuario.")

            playlist = sp.current_user_playlist_create(nombre_playlist, public=False)
            track_uris = []

            for _, row in dataframe_resultados.iterrows():
                query = f"track:{row['track_name']} artist:{row['artist']}"
                result = sp.search(q=query, type='track', limit=1)
                
                if result['tracks']['items']:
                    track_uris.append(result['tracks']['items'][0]['uri'])
                else:
                    query_suave = str(row['track_name'])
                    result_suave = sp.search(q=query_suave, type='track', limit=1)
                    if result_suave['tracks']['items']:
                        track_uris.append(result_suave['tracks']['items'][0]['uri'])
                        
            if track_uris:
                sp.playlist_add_items(playlist['id'], track_uris)
                url_lista = playlist['external_urls']['spotify']
                return {
                    "status": "success",
                    "message": f"Playlist creada con {len(track_uris)} canciones.",
                    "playlist_url": url_lista,
                    "token_info": token_info
                }
            else:
                sp.current_user_unfollow_playlist(playlist['id'])
                return {
                    "status": "error",
                    "message": "No se encontraron coincidencias de esas canciones en Spotify.",
                    "token_info": token_info
                }
                
        except Exception as e:
            return {"status": "error", "message": str(e), "token_info": token_info}

    def extraer_tracks_de_playlist(self, playlist_url, token_info: Optional[dict] = None):
        try:
            # Si hay sesión Spotify, se usa cliente del usuario (permite privadas).
            # Si no, se usa cliente público (solo playlists públicas).
            if token_info:
                sp, token_info = self.get_user_client(token_info)
            elif self.sp:
                sp = self.sp
            else:
                sp = self.get_public_client()
            if not sp:
                return {"tracks": None, "token_info": token_info}

            url_limpia = playlist_url.strip().split('?')[0]
            
            if 'open.spotify.com' in url_limpia:
                parts = [p for p in url_limpia.split('/') if p]
                playlist_id = parts[-1]
            elif 'spotify:playlist:' in url_limpia:
                playlist_id = url_limpia.split(':')[-1]
            else:
                playlist_id = url_limpia

            if len(playlist_id) < 15:
                return {"tracks": None, "token_info": token_info}
            
            resultados = sp.playlist_items(playlist_id)
            
            if not resultados or 'items' not in resultados:
                return {"tracks": None, "token_info": token_info}
                
            lista_nombres = []
            tracks = resultados['items']
            
            for item in tracks:
                track_data = item.get('item') or item.get('track')
                
                if track_data and track_data.get('name'):
                    nombre_track = track_data['name']
                    artistas = track_data.get('artists', [])
                    nombre_artist = artistas[0]['name'] if artistas else "Unknown"
                    lista_nombres.append({'track_name': nombre_track, 'artist': nombre_artist})
                else:
                    if 'name' in item:
                        nombre_track = item['name']
                        artistas = item.get('artists', [])
                        nombre_artist = artistas[0]['name'] if artistas else "Unknown"
                        lista_nombres.append({'track_name': nombre_track, 'artist': nombre_artist})

            temp_res = resultados
            try:
                while temp_res and temp_res.get('next') and len(lista_nombres) < 300:
                    temp_res = sp.next(temp_res)
                    if not temp_res or 'items' not in temp_res: break
                    for item in temp_res['items']:
                        track_data = item.get('item') or item.get('track') or item
                        if track_data and track_data.get('name'):
                            nombre_track = track_data['name']
                            artistas = track_data.get('artists', [])
                            nombre_artist = artistas[0]['name'] if artistas else "Unknown"
                            lista_nombres.append({'track_name': nombre_track, 'artist': nombre_artist})
            except Exception:
                pass
                    
            if not lista_nombres:
                return {"tracks": None, "token_info": token_info}

            return {"tracks": lista_nombres, "token_info": token_info}
            
        except Exception as e:
            print(f"[ERROR] Extrayendo Playlist: {e}")
            return {"tracks": None, "token_info": token_info}

    def _get_best_client(self):
        # Prioriza cliente autenticado de usuario local; fallback a credenciales de app.
        return self.sp if self.sp else self.get_public_client()

    def buscar_y_recomendar_por_query(self, query: str, limit: int = 15):
        """
        Fallback híbrido:
        1) Busca la canción en Spotify.
        2) Usa el primer match como seed para obtener recomendaciones relacionadas.
        3) Devuelve formato compatible con el frontend actual.
        """
        try:
            sp = self._get_best_client()
            
            # Forzar conversión a int de Python puro (evitar numpy.int64 u otros)
            try:
                if hasattr(limit, "item"): # Manejar tipos de numpy
                    limit = limit.item()
                limit = int(limit)
            except:
                limit = 15
            
            # Spotify Search permite max 50. Recommendations permite max 100.
            # Usamos 20 como un límite seguro y estándar.
            safe_limit = int(max(1, min(limit, 50)))
            
            print(f"   [INFO] Buscando seed para: '{query}' (limit={safe_limit})")
            
            # Búsqueda inicial del track para obtener el ID
            search = sp.search(q=query, type="track", limit=1)
            items = search.get("tracks", {}).get("items", [])
            
            seed_id = None
            if items:
                seed_track = items[0]
                seed_id = seed_track.get("id")
                print(f"   [OK] Seed encontrado: {seed_track.get('name')} ({seed_id})")
            else:
                print(f"   [WARN] No se encontró '{query}' en Spotify.")

            rec_tracks = []
            
            # 1. Intentar Recomendaciones (si hay seed_id)
            if seed_id:
                try:
                    rec_resp = sp.recommendations(seed_tracks=[seed_id], limit=safe_limit)
                    rec_tracks = rec_resp.get("tracks", []) or []
                    if rec_tracks:
                        print(f"   [OK] {len(rec_tracks)} recomendaciones obtenidas por seed.")
                except Exception as rec_err:
                    print(f"   [WARN] recommendations() falló (posible 404): {rec_err}")

            # 2. Fallback: Búsqueda Directa (si no hay recs o no hay seed_id)
            if not rec_tracks:
                print(f"   [INFO] Intentando búsqueda directa como fallback para: '{query}'")
                try:
                    # Si falla con safe_limit, intentamos con un valor fijo pequeño (10)
                    try:
                        fallback_search = sp.search(q=query, type="track", limit=safe_limit)
                    except:
                        print(f"   [WARN] Reintentando búsqueda con limit=10 fijo...")
                        fallback_search = sp.search(q=query, type="track", limit=10)
                        
                    rec_tracks = fallback_search.get("tracks", {}).get("items", []) or []
                    if rec_tracks:
                        print(f"   [OK] {len(rec_tracks)} tracks encontrados vía búsqueda directa.")
                except Exception as search_err:
                    print(f"   [ERROR] Fallback de búsqueda también falló: {search_err}")

            out = []
            for idx, track in enumerate(rec_tracks):
                artists = track.get("artists", [])
                artist_name = artists[0]["name"] if artists else "Unknown"
                track_name = track.get("name", "Unknown")
                popularity = float(track.get("popularity", 50))
                match_percent = max(1.0, 100.0 - (idx * 4.0))
                out.append({
                    "track_name": track_name,
                    "artist": artist_name,
                    "popularity": popularity,
                    "track_genre": "N/A",
                    "match_percent": match_percent
                })
            return out
        except Exception as e:
            print(f"   [ERROR] Error crítico en buscar_y_recomendar: {e}")
            return []

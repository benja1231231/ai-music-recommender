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
        # Limpieza de cache al iniciar para forzar re-auth con scopes correctos
        if os.path.exists(".cache"):
            os.remove(".cache")
            print("   [INFO] Cache de Spotify limpiada para refrescar permisos.")

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

        # Scopes expandidos para asegurar permisos de escritura
        # IMPORTANTE: user-read-private y user-read-email son necesarios para identificar al usuario correctamente en dev mode
        scope = "playlist-modify-public playlist-modify-private user-library-modify user-library-read user-read-private user-read-email"
        
        try:
            # Inicialización explícita con manejo de caché forzado
            self.auth_manager = SpotifyOAuth(
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=redirect_uri,
                scope=scope,
                open_browser=True,
                cache_path=".cache",
                show_dialog=True # Forzar diálogo para asegurar que el usuario vea qué cuenta está usando
            )
            
            self.sp = spotipy.Spotify(auth_manager=self.auth_manager)
            
            # Intento de obtener el ID de usuario
            try:
                user_info = self.sp.current_user()
                if user_info:
                    self.user_id = user_info['id']
                    print(f"   [OK] Conectado a Spotify como: {user_info.get('display_name', self.user_id)} ({self.user_id})")
                else:
                    self.user_id = "me"
                    print("   [WARN] Conexion establecida (Usuario no identificado, usando fallback 'me').")
            except spotipy.exceptions.SpotifyException as e:
                if e.http_status == 403:
                    print("\n[CRITICO] Error 403 (Acceso Denegado).")
                    print(f"   [!] El usuario '{self.user_id if hasattr(self, 'user_id') else 'desconocido'}' no tiene permisos para esta App.")
                    print("   [!] REQUISITO: El email de la cuenta Spotify debe estar en 'User Management' del Dashboard de Spotify.")
                    self.user_id = None
                else:
                    raise e
                
        except Exception as e:
            print("\n[ERROR] Error Critico de Conexion a Spotify:")
            print(f"   Detalle: {str(e)}")
            print("   [!] Asegurate de que:")
            print(f"       1. El Client ID y Secret sean correctos.")
            print(f"       2. La Redirect URI sea EXACTAMENTE: {redirect_uri}")
            print(f"       3. Hagas clic en 'Aceptar' en la ventana del navegador que se abre.")
            self.user_id = None

    def exportar_recomendaciones_a_playlist(self, nombre_playlist, dataframe_resultados):
        if not self.user_id:
            print("\n[ERROR] Servicio de Spotify no disponible. Verifica tus credenciales.")
            return

        # Limpiar nombre si es una URL (para mejor UX)
        if "http" in nombre_playlist:
            nombre_playlist = "AI Recs: Playlist Importada"

        print(f"\n[INFO] Contactando satelites de Spotify para construir: '{nombre_playlist}'...")
        
        try:
            # Verificación extendida de usuario
            user_data = self.sp.current_user()
            if not user_data:
                raise Exception("No se pudo obtener la información del usuario.")
                
            uid = user_data['id']
            u_email = user_data.get('email', 'Oculto')
            u_product = user_data.get('product', 'Desconocido')
            print(f"   [INFO] Perfil: {user_data.get('display_name')} | ID: {uid} | Email: {u_email}")
            print(f"   [INFO] Tipo de cuenta: {u_product}")
            
            # Nuclear Option: Si hay scopes pero falla, forzar refresh
            token_info = self.auth_manager.get_cached_token()
            if token_info:
                print(f"   [DEBUG] Scopes en token: {token_info.get('scope')}")
            
            # Prueba de lectura previa (¿Podemos ver las playlists?)
            try:
                print(f"   [INFO] Verificando permisos de LECTURA (GET)...")
                playlists_count = len(self.sp.current_user_playlists(limit=1)['items'])
                print(f"   [OK] Lectura exitosa. Permisos basicos OK.")
            except Exception as e:
                print(f"   [!] FALLO LECTURA: {e}")
                print("   [!] Esto indica que el TOKEN es invalido para este usuario.")

            # Intento de creación con endpoint /me/ (mas robusto que /users/{id}/)
            try:
                print(f"   [INFO] Intento 1: Creando playlist via endpoint /me/...")
                playlist = self.sp.current_user_playlist_create(nombre_playlist, public=False)
            except spotipy.exceptions.SpotifyException as e:
                if e.http_status == 403:
                    print("   [WARN] Fallo /me/ private. Intento 2: Creando via /me/ public...")
                    playlist = self.sp.current_user_playlist_create(nombre_playlist, public=True)
                else:
                    raise e
            
            track_uris = []
            print(f"   [INFO] Buscando {len(dataframe_resultados)} canciones en Spotify...")
            
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
                print(f"\n[OK] EXITO! Playlist creada en tu cuenta con {len(track_uris)} hermosas canciones.")
                print(f"👉 Enlace: {url_lista}")
                # Abre el navegador automáticamente (Magia UX)
                webbrowser.open(url_lista)
            else:
                print("\n[ERROR] No se encontraron coincidencias exactas en la base de Spotify para esos tracks.")
                self.sp.user_playlist_unfollow(self.user_id, playlist['id']) # Borra la lista si quedó vacía
                
        except spotipy.exceptions.SpotifyException as e:
            if e.http_status == 403:
                print(f"\n[ERROR 403] Spotify bloqueo la accion.")
                print("   [!] CAUSA PROBABLE: El email NO es el que pusiste en el Dashboard.")
                print("   [!] ACCION: Borra el archivo '.cache' y reinicia el servidor.")
            print(f"\n[ERROR] Al exportar: {e}")
        except Exception as e:
            print(f"\n[ERROR] General: {e}")

    def extraer_tracks_de_playlist(self, playlist_url):
        if not self.user_id:
            print("\n[ERROR] Servicio de Spotify no disponible. Verifica tus credenciales.")
            return None

        print(f"\n[INFO] Analizando link: {playlist_url}")
        try:
            # Soporte ultra-robusto para múltiples formatos de URL de Spotify
            url_limpia = playlist_url.strip().split('?')[0] # Quita espacios y parámetros URL
            
            if 'open.spotify.com' in url_limpia:
                # Caso: https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M
                # O Caso: https://open.spotify.com/intl-es/playlist/37i9dQZF1DXcBWIGoYBM5M
                parts = [p for p in url_limpia.split('/') if p] # Filtra partes vacías (ej: trailing slash)
                playlist_id = parts[-1]
            elif 'spotify:playlist:' in url_limpia:
                playlist_id = url_limpia.split(':')[-1]
            else:
                playlist_id = url_limpia

            print(f"   [INFO] ID Extraido: {playlist_id}")
            
            if len(playlist_id) < 15:
                print(f"   [ERROR] ID '{playlist_id}' parece invalido (demasiado corto).")
                return None
            
            print(f"   [INFO] Llamando a API de Spotify para ID: {playlist_id}...")
            resultados = self.sp.playlist_tracks(playlist_id)
            
            if not resultados or 'items' not in resultados:
                print(f"   [ERROR] La API no devolvio tracks para el ID: {playlist_id}")
                return None
                
            lista_nombres = []
            tracks = resultados['items']
            print(f"   [OK] Encontrados {len(tracks)} tracks iniciales.")
            
            # Procesar tracks de la primera página
            for item in tracks:
                # La key correcta segun el debug es 'item', no 'track'
                track_data = item.get('item') or item.get('track')
                
                if track_data and track_data.get('name'):
                    nombre_track = track_data['name']
                    artistas = track_data.get('artists', [])
                    nombre_artist = artistas[0]['name'] if artistas else "Unknown"
                    lista_nombres.append({'track_name': nombre_track, 'artist': nombre_artist})
                    print(f"      + {nombre_track} - {nombre_artist}")
                else:
                    # Intento desesperado: buscar name en la raiz si 'item' falló
                    if 'name' in item:
                        nombre_track = item['name']
                        artistas = item.get('artists', [])
                        nombre_artist = artistas[0]['name'] if artistas else "Unknown"
                        lista_nombres.append({'track_name': nombre_track, 'artist': nombre_artist})
                        print(f"      + {nombre_track} - {nombre_artist}")
                    else:
                        print(f"      - Saltando item sin 'item'/'track' key. Keys: {item.keys()}")

            # Paginación para listas largas
            temp_res = resultados
            try:
                while temp_res and temp_res.get('next') and len(lista_nombres) < 300:
                    print(f"   [INFO] Cargando pagina siguiente (Total actual: {len(lista_nombres)})...")
                    temp_res = self.sp.next(temp_res)
                    if not temp_res or 'items' not in temp_res: break
                    for item in temp_res['items']:
                        track_data = item.get('item') or item.get('track') or item
                        if track_data and track_data.get('name'):
                            nombre_track = track_data['name']
                            artistas = track_data.get('artists', [])
                            nombre_artist = artistas[0]['name'] if artistas else "Unknown"
                            lista_nombres.append({'track_name': nombre_track, 'artist': nombre_artist})
            except Exception as next_err:
                print(f"   [WARN] Error en paginacion: {next_err}. Usando canciones obtenidas hasta ahora.")
                    
            if not lista_nombres:
                print(f"   [ERROR] No se pudieron extraer nombres validos de los {len(tracks)} items.")
                return None
            
            print(f"   [OK] Total final: {len(lista_nombres)} canciones extraidas con exito.")
            
            # NOTA DE SEGURIDAD: Ya no pedimos sp.audio_features() porque Spotify revoca o bloquea 
            # esos endpoints avanzados a cuentas gratuitas o les tira errores 'Forbidden'.
            # Ahora devolveremos los nombres limpios y calcularemos la genética acústica de manera LOCAL.
            
            return lista_nombres
            
        except Exception as e:
            print("[ERROR] Extrayendo Playlist. Asegurate que el link sea publico y no sea exclusivo Premium.")
            print(f"Detalle Tecnico: {e}")
            return None
            
            # NOTA DE SEGURIDAD: Ya no pedimos sp.audio_features() porque Spotify revoca o bloquea 
            # esos endpoints avanzados a cuentas gratuitas o les tira errores 'Forbidden'.
            # Ahora devolveremos los nombres limpios y calcularemos la genética acústica de manera LOCAL.
            
            return lista_nombres
            
        except Exception as e:
            print("❌ Error extrayendo Playlist. Asegúrate que el link sea público y no sea exclusivo Premium.")
            print(f"Detalle Técnico: {e}")
            return None

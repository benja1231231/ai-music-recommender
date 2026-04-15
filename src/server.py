from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel
import uvicorn
import os
import sys
import pandas as pd

# Asegurar que reconozca los módulos en src/
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from recommender import MusicRecommender

app = FastAPI(title="AI Music Recommender API")
session_secret = os.getenv("APP_SESSION_SECRET", "change-this-in-production")
app.add_middleware(SessionMiddleware, secret_key=session_secret, same_site="lax")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOWED_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

print("Iniciando Motor AI para Web...")
motor = MusicRecommender()

# Ruta local del dataset
engine_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'spotify_data.csv')

if os.path.exists(engine_path):
    motor.preparar_dataset(engine_path)
else:
    print(f"[WARN] Dataset no encontrado en {engine_path}. Cargando modo prueba.")
    motor.preparar_dataset()

from typing import Optional

class QueryRequest(BaseModel):
    query: str
    mode: str = "nlp" # "contenido", "nlp", "spotify_import"
    override_type: Optional[str] = None
    override_index: Optional[int] = None

class ExportRequest(BaseModel):
    playlist_name: str
    tracks: list # Lista de dicts con track_name y artist

@app.post("/api/recommend")
async def recommend(request_data: QueryRequest, request: Request):
    print(f"Buscando: '{request_data.query}' en modo: {request_data.mode}")
    try:
        spotify_token = request.session.get("spotify_token")
        resultado = motor.recomendar(
            request_data.query,
            modo=request_data.mode,
            exportar=True, # Forzar 15 resultados siempre para que exportar funcione bien
            override_type=request_data.override_type,
            override_index=request_data.override_index,
            spotify_token=spotify_token
        )
        
        if isinstance(resultado, dict):
            if resultado.get("status") == "success":
                df_resultados = resultado["data"]
                print(f"[OK] Exito: {len(df_resultados)} resultados encontrados.")
                cols = ['track_name', 'artist', 'popularity', 'track_genre', 'match_percent']
                exist_cols = [c for c in cols if c in df_resultados.columns]
                
                # Asegurar que los datos sean serializables y no contengan NaNs o tipos raros
                import numpy as np
                df_clean = df_resultados[exist_cols].copy()
                # Convertir floats de numpy a nativos de python
                for col in df_clean.select_dtypes(include=['float32', 'float64']).columns:
                    df_clean[col] = df_clean[col].astype(float)
                
                lista_datos = df_clean.fillna("N/A").to_dict(orient='records')
                
                # Limpiar chart_data también
                chart_data = resultado.get("chart_data", {})
                if chart_data:
                    for key in ['target', 'recommendations']:
                        if key in chart_data:
                            chart_data[key] = {k: float(v) if isinstance(v, (np.float32, np.float64)) else v for k, v in chart_data[key].items()}

                return {
                    "status": "success",
                    "data": lista_datos,
                    "chart_data": chart_data
                }
            return resultado
            
        return {"status": "error", "message": "Respuesta inesperada del motor."}
    except Exception as e:
        import traceback
        print(f"[ERROR CRITICO] {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/export")
async def export_to_spotify(request_data: ExportRequest, request: Request):
    if not motor.spotify:
        return {"status": "error", "message": "Spotify no configurado en el servidor."}

    spotify_token = request.session.get("spotify_token")
    
    try:
        df_export = pd.DataFrame(request_data.tracks)
        result = motor.spotify.exportar_recomendaciones_a_playlist(
            request_data.playlist_name,
            df_export,
            spotify_token
        )
        if result.get("token_info"):
            request.session["spotify_token"] = result["token_info"]
        if result.get("status") == "success":
            return {
                "status": "success",
                "message": result["message"],
                "playlist_url": result.get("playlist_url")
            }
        return {"status": "error", "message": result.get("message", "Error exportando playlist")}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/spotify/login")
async def spotify_login():
    if not motor.spotify:
        raise HTTPException(status_code=503, detail="Spotify no configurado en este servidor.")
    auth_url = motor.spotify.get_authorize_url()
    return {"status": "success", "auth_url": auth_url}

@app.get("/api/spotify/callback")
async def spotify_callback(code: str, request: Request):
    if not motor.spotify:
        raise HTTPException(status_code=503, detail="Spotify no configurado en este servidor.")
    try:
        token_info = motor.spotify.exchange_code(code)
        request.session["spotify_token"] = token_info
        frontend_redirect = os.getenv("FRONTEND_URL", "/")
        return RedirectResponse(url=f"{frontend_redirect}?spotify=connected")
    except Exception as e:
        frontend_redirect = os.getenv("FRONTEND_URL", "/")
        return RedirectResponse(url=f"{frontend_redirect}?spotify=error&message={str(e)}")

@app.get("/api/spotify/status")
async def spotify_status(request: Request):
    if not motor.spotify:
        return {"status": "error", "connected": False, "message": "Spotify no configurado."}
    token_info = request.session.get("spotify_token")
    if not token_info and getattr(motor.spotify, "user_id", None):
        return {
            "status": "success",
            "connected": True,
            "user": {
                "id": motor.spotify.user_id,
                "display_name": motor.spotify.user_id
            },
            "mode": "server_local"
        }
    if not token_info:
        return {"status": "success", "connected": False}
    user_info, refreshed_token = motor.spotify.get_current_user(token_info)
    if refreshed_token:
        request.session["spotify_token"] = refreshed_token
    if not user_info:
        return {"status": "success", "connected": False}
    return {
        "status": "success",
        "connected": True,
        "user": {
            "id": user_info.get("id"),
            "display_name": user_info.get("display_name") or user_info.get("id")
        }
    }

@app.post("/api/spotify/logout")
async def spotify_logout(request: Request):
    request.session.pop("spotify_token", None)
    return {"status": "success", "connected": False}

frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'public'))
if not os.path.exists(frontend_path):
    os.makedirs(frontend_path)

# Montar frontend para que corra en el puerto 8000
app.mount("/", StaticFiles(directory=frontend_path, html=True), name="public")

if __name__ == "__main__":
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)

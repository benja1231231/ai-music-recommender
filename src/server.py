from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import os
import sys
import pandas as pd

# Asegurar que reconozca los módulos en src/
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from recommender import MusicRecommender

app = FastAPI(title="AI Music Recommender API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
async def recommend(request: QueryRequest):
    print(f"Buscando: '{request.query}' en modo: {request.mode}")
    try:
        resultado = motor.recomendar(
            request.query, 
            modo=request.mode, 
            exportar=True, # Forzar 15 resultados siempre para que exportar funcione bien
            override_type=request.override_type, 
            override_index=request.override_index
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
async def export_to_spotify(request: ExportRequest):
    if not motor.spotify:
        return {"status": "error", "message": "Spotify no configurado en el servidor."}
    
    try:
        df_export = pd.DataFrame(request.tracks)
        motor.spotify.exportar_recomendaciones_a_playlist(request.playlist_name, df_export)
        return {"status": "success", "message": "¡Playlist creada con éxito!"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'public'))
if not os.path.exists(frontend_path):
    os.makedirs(frontend_path)

# Montar frontend para que corra en el puerto 8000
app.mount("/", StaticFiles(directory=frontend_path, html=True), name="public")

if __name__ == "__main__":
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)

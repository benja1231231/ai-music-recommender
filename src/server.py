from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import os
import sys

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
engine_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'spotify_data.csv'))
try:
    motor.preparar_dataset(engine_path)
except Exception as e:
    print(f"Advertencia: {e}")
    # Intenta con ruta generica si falla
    motor.preparar_dataset()

from typing import Optional

class QueryRequest(BaseModel):
    query: str
    mode: str = "nlp" # "contenido" o "nlp"
    override_type: Optional[str] = None
    override_index: Optional[int] = None

@app.post("/api/recommend")
async def recommend(request: QueryRequest):
    try:
        resultado = motor.recomendar(
            request.query, 
            modo=request.mode, 
            override_type=request.override_type, 
            override_index=request.override_index
        )
        
        # Si devuelve Diccionario directo (Éxito con Radar o Conflicto)
        if isinstance(resultado, dict):
            if resultado.get("status") == "success":
                df_resultados = resultado["data"]
                cols = ['track_name', 'artist', 'popularity', 'track_genre', 'match_percent']
                exist_cols = [c for c in cols if c in df_resultados.columns]
                lista_datos = df_resultados[exist_cols].fillna("N/A").to_dict(orient='records')
                
                return {
                    "status": "success",
                    "data": lista_datos,
                    "chart_data": resultado.get("chart_data", {})
                }
            return resultado
            
        if resultado is None or resultado.empty:
            return {"status": "error", "message": "No se encontraron resultados que coincidan."}
            
        resultados = resultado[['track_name', 'artist', 'popularity', 'track_genre']].fillna("N/A").to_dict(orient='records')
        return {"status": "success", "data": resultados}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'public'))
if not os.path.exists(frontend_path):
    os.makedirs(frontend_path)

# Montar frontend para que corra en el puerto 8000
app.mount("/", StaticFiles(directory=frontend_path, html=True), name="public")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=True)

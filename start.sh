#!/usr/bin/env bash
set -e
mkdir -p data
if [ ! -f data/spotify_data.csv ]; then
  if [ -z "https://www.dropbox.com/scl/fi/o79svfb998b3lghaa85f4/spotify_data.csv?rlkey=gvrsq5dnmjyibi449gff65a8h&st=iyge7gtm?raw=1" ]; then
    echo "ERROR: DATASET_URL no está configurada"
    exit 1
  fi
  echo "Descargando dataset..."
  curl -L "https://www.dropbox.com/scl/fi/o79svfb998b3lghaa85f4/spotify_data.csv?rlkey=gvrsq5dnmjyibi449gff65a8h&st=iyge7gtm?raw=1" -o data/spotify_data.csv
fi
echo "Iniciando API..."
exec uvicorn src.server:app --host 0.0.0.0 --port $PORT
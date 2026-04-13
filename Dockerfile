# Imagen base oficial de Python (Slim para ahorrar espacio)
FROM python:3.11-slim

# Evitar que Python genere archivos .pyc y permitir logs en tiempo real
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Directorio de trabajo en el contenedor
WORKDIR /app

# Instalar dependencias del sistema necesarias para algunas librerías de Python
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements primero para aprovechar la caché de Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código del proyecto
COPY . .

# Exponer el puerto que usará FastAPI
EXPOSE 8000

# Comando para ejecutar la aplicación en producción
# Aumentamos el timeout a 120s para permitir la carga del dataset en el primer inicio
CMD ["gunicorn", "src.server:app", "--workers", "1", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "--timeout", "120"]

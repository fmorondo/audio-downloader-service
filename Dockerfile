# Dockerfile
# Usamos una imagen base de Python ligera (Python 3.10 o superior)
FROM python:3.10-slim

# 1. Instalar ffmpeg: Es esencial para que yt-dlp pueda extraer el audio
# y convertirlo al formato final (e.g., MP3).
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# 2. Configuración del espacio de trabajo
WORKDIR /app
COPY requirements.txt .

# 3. Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copiar el resto del código
COPY . .

# 5. Especificar el puerto de Cloud Run
# Cloud Run inyecta la variable de entorno PORT, pero el estándar es 8080
EXPOSE 8080

# 6. Comando de ejecución: Inicia el servidor Flask
# Llamaremos a nuestro archivo principal 'main.py'
CMD ["python", "main.py"]
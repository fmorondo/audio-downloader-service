# Dockerfile
# Usamos una imagen base de Python ligera (Python 3.10 o superior)
FROM python:3.10-slim

# 1. Instalar ffmpeg: Es esencial para que yt-dlp pueda extraer el audio
# y convertirlo al formato final (e.g., MP3).
# curl/unzip son necesarios solo para instalar Deno en el paso siguiente.
RUN apt-get update && \
    apt-get install -y ffmpeg curl unzip && \
    rm -rf /var/lib/apt/lists/*

# 1.b Instalar Deno: yt-dlp lo usa como runtime de JavaScript para resolver
# el "n challenge" que YouTube exige desde 2025 antes de servir los formatos
# de audio/video (ver https://github.com/yt-dlp/yt-dlp/wiki/EJS). Sin esto,
# yt-dlp solo consigue miniaturas y falla con "Requested format is not available".
RUN curl -fsSL https://deno.land/install.sh | DENO_INSTALL=/usr/local sh

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
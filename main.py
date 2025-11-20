# main.py
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import os
import logging
from downloader import download_audio_from_url # Importa la lógica del paso 3

# Configuración y Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Inicialización de Flask
app = Flask(__name__)

# Configuración de CORS
# MUY IMPORTANTE: Cambia "https://fmorondo.github.io" por el dominio exacto
# donde se aloja tu frontend si es diferente.
CORS(app, resources={r"/*": {"origins": [
    "https://fmorondo.github.io",
    "http://localhost:3000" # Útil para pruebas locales
]}})

@app.route("/", methods=["GET"])
def home():
    """Ruta simple de salud del servicio."""
    return "🎧 Servicio de descarga de audio (yt-dlp) activo. Usa la ruta /download."

@app.route("/download", methods=["POST", "OPTIONS"])
def download_audio_api():
    """
    Ruta principal para recibir la URL y devolver el archivo MP3.
    """
    # Manejo de la pre-petición CORS (preflight)
    if request.method == "OPTIONS":
        return ("", 204)
        
    url = None
    try:
        # 1. Obtener la URL del cuerpo JSON
        data = request.get_json(silent=True)
        url = data.get("url")
        
        if not url:
            return jsonify({"error": "Falta la clave 'url' en el cuerpo de la petición JSON."}), 400
            
        logger.info(f"Petición recibida para descargar audio: {url}")
        
        # 2. Ejecutar la descarga
        # La función devuelve la ruta absoluta del archivo MP3 en /tmp
        ruta_local_mp3 = download_audio_from_url(url, output_dir="/tmp")
        
        # 3. Preparar la respuesta y el envío
        
        # Determina un nombre de archivo seguro para el cliente (sin ruta)
        nombre_archivo_base = os.path.basename(ruta_local_mp3)
        
        logger.info(f"Descarga exitosa. Enviando archivo al cliente: {nombre_archivo_base}")
        
        # 4. Devolver el archivo como adjunto
        return send_file(
            ruta_local_mp3,
            as_attachment=True,
            download_name=nombre_archivo_base,
            mimetype="audio/mp3"
        )
            
    except Exception as e:
        logger.error(f"Error en la descarga para URL: {url if url else 'N/A'}", exc_info=True)
        # 500 es el código de error genérico. Para vídeos muy largos,
        # puede llegar un 504 por timeout del Cloud Run.
        return jsonify({"error": f"Error al procesar la descarga: {str(e)}. "
                                 f"Comprueba la URL y el Timeout de Cloud Run."}), 500

if __name__ == "__main__":
    # Cloud Run usa la variable de entorno PORT, si no existe usa 8080 (el puerto expuesto en Dockerfile)
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
# downloader.py
import yt_dlp
import os
import uuid
import logging

# Configuración básica de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def download_audio_from_url(url: str, output_dir: str = "/tmp") -> str:
    """
    Descarga la pista de audio de un vídeo usando yt-dlp, convierte a MP3,
    y retorna la ruta local (en /tmp) del archivo de audio descargado.
    """
    
    # Generamos un ID único para nombrar el archivo temporal de forma segura
    unique_id = uuid.uuid4().hex[:12]
    # Define la plantilla para el nombre de archivo antes del post-procesamiento
    temp_filename_template = os.path.join(output_dir, f'{unique_id}.%(ext)s')
    
    final_mp3_path = None
    
    # 📝 Hook para capturar la ruta final del archivo MP3
    # yt-dlp renombra el archivo después del post-procesamiento con ffmpeg.
    def hook(d):
        nonlocal final_mp3_path
        if d['status'] == 'finished' and d.get('info_dict'):
            # El postprocessor (FFmpegExtractAudio) crea el archivo final.
            # Intentamos deducir el nombre final que debería tener el MP3
            # basado en el nombre de archivo original y la extensión mp3.
            try:
                base = os.path.splitext(d['filename'])[0]
                potential_path = f"{base}.mp3"
                if os.path.exists(potential_path):
                    final_mp3_path = potential_path
            except Exception as e:
                logger.error(f"Error en el hook de post-proceso: {e}")


    # Opciones de yt-dlp:
    ydl_opts = {
        'format': 'bestaudio/best',             # Selecciona el mejor formato de audio
        'outtmpl': temp_filename_template,      # Plantilla para la salida
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',          # Calidad de audio (Kbps)
        }],
        'progress_hooks': [hook],
        'noplaylist': True,                     # Ignorar listas de reproducción
        'quiet': True,                          # Suprimir la salida de la consola de yt-dlp
        'cachedir': False,                      # Desactivar caché (importante en contenedores)
    }

    logger.info(f"Descargando audio de: {url}")
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            # Fallback si el hook no funciona perfectamente (depende de la versión)
            if not final_mp3_path and 'requested_downloads' in info_dict:
                 for item in info_dict['requested_downloads']:
                    if item.get('filepath', '').endswith('.mp3'):
                        final_mp3_path = item['filepath']
                        break
            
            # Último fallback si no se ha encontrado la ruta
            if not final_mp3_path:
                logger.warning("Ruta MP3 no detectada por el hook. Intentando deducir de info_dict...")
                potential_base = os.path.splitext(info_dict['filepath'])[0]
                final_mp3_path = f"{potential_base}.mp3"
                
                if not os.path.exists(final_mp3_path):
                     raise Exception(f"La descarga no produjo un archivo MP3 en la ruta esperada: {final_mp3_path}")


        if not os.path.exists(final_mp3_path):
            raise Exception("El archivo MP3 final no se pudo encontrar tras la descarga/conversión.")

        logger.info(f"Descarga exitosa. Archivo MP3 guardado en: {final_mp3_path}")
        return final_mp3_path

    except yt_dlp.utils.DownloadError as e:
        logger.error(f"Error de descarga: {e}")
        # Simplificamos el error para el cliente
        raise Exception(f"Error al procesar la URL. Posiblemente contenido no disponible o URL no válida.")
        
    except Exception as e:
        logger.error(f"Error inesperado: {e}")
        raise
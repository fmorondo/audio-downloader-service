# downloader.py
import html
import logging
import os
import re
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import uuid

import yt_dlp

# Configuración básica de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BROWSER_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
)
NAVARRA_WATCH_HOST = "grabaciones.parlamentodenavarra.es"


def _download_single_audio_source(url: str, output_dir: str = "/tmp") -> str:
    """Descarga una única fuente multimedia y devuelve la ruta final en MP3."""
    unique_id = uuid.uuid4().hex[:12]
    temp_filename_template = os.path.join(output_dir, f"{unique_id}.%(ext)s")
    final_mp3_path = None

    def hook(d):
        nonlocal final_mp3_path
        if d["status"] == "finished" and d.get("info_dict"):
            try:
                base = os.path.splitext(d["filename"])[0]
                potential_path = f"{base}.mp3"
                if os.path.exists(potential_path):
                    final_mp3_path = potential_path
            except Exception as e:
                logger.error(f"Error en el hook de post-proceso: {e}")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": temp_filename_template,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
        "progress_hooks": [hook],
        "noplaylist": True,
        "quiet": True,
        "cachedir": False,
        "http_headers": {
            "User-Agent": BROWSER_USER_AGENT,
        },
    }

    logger.info(f"Descargando audio de la fuente resuelta: {url}")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            if not final_mp3_path and "requested_downloads" in info_dict:
                for item in info_dict["requested_downloads"]:
                    if item.get("filepath", "").endswith(".mp3"):
                        final_mp3_path = item["filepath"]
                        break

            if not final_mp3_path:
                logger.warning("Ruta MP3 no detectada por el hook. Intentando deducir de info_dict...")
                potential_base = os.path.splitext(info_dict["filepath"])[0]
                final_mp3_path = f"{potential_base}.mp3"

                if not os.path.exists(final_mp3_path):
                    raise Exception(
                        f"La descarga no produjo un archivo MP3 en la ruta esperada: {final_mp3_path}"
                    )

        if not os.path.exists(final_mp3_path):
            raise Exception("El archivo MP3 final no se pudo encontrar tras la descarga/conversión.")

        logger.info(f"Descarga exitosa. Archivo MP3 guardado en: {final_mp3_path}")
        return final_mp3_path

    except yt_dlp.utils.DownloadError as e:
        logger.error(f"Error de descarga: {e}")
        raise Exception(f"Error al procesar la URL. Posiblemente contenido no disponible o URL no válida.")

    except Exception as e:
        logger.error(f"Error inesperado: {e}")
        raise


def _html_unescape_js(value: str) -> str:
    return html.unescape(value.replace("\\/", "/").replace("\\'", "'"))


def _fetch_html(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": BROWSER_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")
    except urllib.error.HTTPError as exc:
        raise Exception(f"No se pudo abrir la página de Navarra (HTTP {exc.code}).") from exc
    except urllib.error.URLError as exc:
        raise Exception("No se pudo conectar con la página de Navarra.") from exc


def _parse_navarra_entries(html_text: str) -> list[dict]:
    entries = []
    entry_blocks = re.finditer(
        r"JSPLAYLIST1\[(\d+)\]\s*=\s*\{\};(.*?)(?=JSPLAYLIST1\[\d+\]\s*=\s*\{\};|</script>)",
        html_text,
        re.DOTALL,
    )

    for block in entry_blocks:
        sequence = int(block.group(1))
        body = block.group(2)

        def extract(field: str) -> str | None:
            match = re.search(rf"JSPLAYLIST1\[{sequence}\]\.{field}='([^']*)';", body)
            if not match:
                return None
            return _html_unescape_js(match.group(1))

        media_url = extract("media_url")
        if not media_url:
            continue

        entries.append(
            {
                "sequence": sequence,
                "media_url": media_url,
                "watch_id": extract("watch_id"),
                "share_url": extract("share_url"),
                "title": extract("title"),
            }
        )

    return sorted(entries, key=lambda entry: entry["sequence"])


def _normalize_watch_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    scheme = parsed.scheme or "https"
    host = (parsed.hostname or "").lower()
    port = ""
    if parsed.port and parsed.port not in (80, 443):
        port = f":{parsed.port}"
    path = parsed.path or "/"
    query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    normalized_query = urllib.parse.urlencode(
        [(key, value) for key in sorted(query) for value in sorted(query[key])]
    )
    return urllib.parse.urlunparse((scheme, f"{host}{port}", path, "", normalized_query, ""))


def _resolve_navarra_media_urls(url: str) -> list[str]:
    parsed_url = urllib.parse.urlparse(url)
    if (parsed_url.hostname or "").lower() != NAVARRA_WATCH_HOST or parsed_url.path != "/watch":
        return [url]

    html_text = _fetch_html(url)
    entries = _parse_navarra_entries(html_text)
    if not entries:
        raise Exception("No se encontraron pistas multimedia en la página del Parlamento de Navarra.")

    requested_id = urllib.parse.parse_qs(parsed_url.query).get("id", [None])[0]
    normalized_input_url = _normalize_watch_url(url)

    for entry in entries:
        share_url = entry.get("share_url")
        if entry.get("watch_id") == requested_id:
            return [entry["media_url"]]
        if share_url and _normalize_watch_url(share_url) == normalized_input_url:
            return [entry["media_url"]]

    return [entry["media_url"] for entry in entries]


def _concat_mp3_files(file_paths: list[str], output_dir: str) -> str:
    final_path = os.path.join(output_dir, f"{uuid.uuid4().hex[:12]}_merged.mp3")
    concat_list_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".txt",
            prefix="concat_",
            dir=output_dir,
            delete=False,
            encoding="utf-8",
        ) as concat_file:
            concat_list_path = concat_file.name
            for path in file_paths:
                safe_path = path.replace("'", "'\\''")
                concat_file.write(f"file '{safe_path}'\n")

        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                concat_list_path,
                "-vn",
                "-codec:a",
                "libmp3lame",
                "-b:a",
                "192k",
                final_path,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        return final_path
    except subprocess.CalledProcessError as exc:
        logger.error("FFmpeg no pudo concatenar los audios: %s", exc.stderr)
        raise Exception("No se pudieron unir los distintos tramos del audio.") from exc
    finally:
        if concat_list_path and os.path.exists(concat_list_path):
            os.remove(concat_list_path)


def download_audio_from_url(url: str, output_dir: str = "/tmp") -> str:
    """
    Descarga la pista de audio de un vídeo usando yt-dlp, convierte a MP3,
    y retorna la ruta local del archivo de audio descargado.
    """
    resolved_urls = _resolve_navarra_media_urls(url)
    logger.info("Se han resuelto %s fuente(s) multimedia para la URL recibida.", len(resolved_urls))

    downloaded_paths = [_download_single_audio_source(media_url, output_dir=output_dir) for media_url in resolved_urls]

    if len(downloaded_paths) == 1:
        return downloaded_paths[0]

    return _concat_mp3_files(downloaded_paths, output_dir=output_dir)

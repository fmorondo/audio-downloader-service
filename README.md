# audio-downloader-service

Servicio Flask para descargar audio con `yt-dlp` y devolverlo como MP3.

## Soporte adicional

También resuelve URLs de la mediateca del Parlamento de Navarra, por ejemplo:

`https://grabaciones.parlamentodenavarra.es/watch?id=ZTIyODE1YzQtNjljMC00NzEwLWFmMmMtZTlkZDM2OWE3MjNh`

Para esas páginas el backend:

- lee el HTML público con cabeceras de navegador,
- extrae los `media_url` HLS embebidos en `JSPLAYLIST1`,
- descarga el audio de cada tramo,
- y si la sesión tiene varios vídeos, los concatena en un único MP3.

## Límite conocido

Este soporte depende de que la página siga entregando el HTML al backend con un `User-Agent` de navegador. Si Cloudflare o la propia web endurecen el acceso, podría hacer falta resolverlo con cookies de sesión o un navegador automatizado.

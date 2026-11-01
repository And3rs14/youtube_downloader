# YouTube Downloader Bot

Bot de Telegram que descarga video o audio (MP3) desde YouTube, TikTok, Instagram, Twitter/X, Facebook y cualquier otro sitio soportado por [yt-dlp](https://github.com/yt-dlp/yt-dlp).

## Funcionamiento

1. Envía un enlace al bot.
2. El bot muestra título, canal, duración y miniatura.
3. Eliges **Video** (mejor calidad, 1080p, 720p o 480p) o **Audio MP3** (baja 128 kbps, media 192 kbps o alta 320 kbps).
4. Verás una barra de progreso durante la descarga y el estado de la subida.
5. Recibes el archivo en el chat. Límite de Telegram para bots: 50 MB.

## Requisitos

- Python 3.12
- `ffmpeg` (conversión a MP3 y unión de video + audio)
- `deno` (runtime JavaScript que yt-dlp necesita para YouTube)
- Un token de bot creado con [@BotFather](https://t.me/BotFather)

## Instalación con conda

```bash
conda env create -f environment.yml
conda activate youtube_downloader
cp .env.example .env   # y pon tu BOT_TOKEN dentro
python telegram_bot.py
```

`environment.yml` instala `ffmpeg` y `deno` desde conda-forge y las dependencias de Python con pip.

## Instalación con pip

Instala `ffmpeg` y `deno` por tu cuenta y luego:

```bash
pip install -r requirements.txt
cp .env.example .env   # y pon tu BOT_TOKEN dentro
python telegram_bot.py
```

## Configuración

El token se lee del archivo `.env`, que está en `.gitignore` y nunca debe subirse al repositorio:

```
BOT_TOKEN=123456789:ABCdef...
```

## Docker

`Dockerfile.coolify` construye una imagen lista para desplegar en Coolify o cualquier host Docker. Define la variable de entorno `BOT_TOKEN` en el servicio.

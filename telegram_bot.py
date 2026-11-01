import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import yt_dlp
import asyncio
import time
from telegram.constants import ChatAction
from telegram.error import TimedOut
from dotenv import load_dotenv

load_dotenv()

# Configurar logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Token del bot (se lee del archivo .env)
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise SystemExit("Falta BOT_TOKEN: define el token en el archivo .env")

# Timeout (segundos) para subir archivos a Telegram. Un archivo de 50 MB en una
# conexion lenta puede tardar varios minutos; el timeout general de 30 s no basta.
MEDIA_UPLOAD_TIMEOUT = 900

# Calidades de audio MP3 (bitrate en kbps)
AUDIO_QUALITIES = {
    "audio_low": "128",
    "audio_mid": "192",
    "audio_high": "320",
}

# Carpeta de descargas
DOWNLOAD_DIR = os.path.join(os.getcwd(), "downloads")
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

# Almacenamiento temporal de URLs por usuario
user_urls = {}


def format_seconds(seconds):
    """Formatea segundos a HH:MM:SS o MM:SS"""
    if not seconds:
        return "00:00"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h:d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start"""
    welcome_message = (
        "🎬 *Descargador Universal Bot*\n\n"
        "Envíame un enlace de YouTube, TikTok, Instagram, etc. y te ayudaré a descargarlo.\n\n"
        "*Comandos:*\n"
        "/start - Mostrar este mensaje\n"
        "/help - Ayuda\n\n"
        "Simplemente pega un enlace para comenzar!"
    )
    await update.message.reply_text(welcome_message, parse_mode='Markdown')


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /help"""
    help_text = (
        "📖 *Cómo usar el bot:*\n\n"
        "1. Envía un enlace de video (YouTube, TikTok, Instagram, etc.)\n"
        "2. El bot analizará el enlace y mostrará la información\n"
        "3. Selecciona el formato (Video o Audio MP3)\n"
        "4. Selecciona la calidad deseada\n"
        "5. Espera a que se descargue y recibe el archivo!\n\n"
        "*Plataformas soportadas:*\n"
        "YouTube, TikTok, Instagram, Twitter/X, Facebook, y más..."
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')


async def get_video_info(url: str) -> dict:
    """Obtiene información del video"""
    ydl_opts = {'quiet': True, 'skip_download': True}
    try:
        loop = asyncio.get_event_loop()
        def extract():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=False)
        return await loop.run_in_executor(None, extract)
    except Exception as e:
        logger.error(f"Error obteniendo info: {e}")
        return None


async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja URLs enviadas por el usuario"""
    url = update.message.text.strip()
    user_id = update.effective_user.id

    status_msg = await update.message.reply_text("🔍 Analizando enlace...")

    # Obtener información del video
    info = await get_video_info(url)

    if not info:
        await status_msg.edit_text("❌ No pude obtener información del video. Verifica el enlace.")
        return

    # Guardar URL para el usuario
    user_urls[user_id] = {'url': url, 'info': info}

    # Preparar mensaje con información
    title = info.get('title', 'Sin título')[:100]
    duration = format_seconds(info.get('duration'))
    uploader = info.get('uploader', 'Desconocido')

    info_text = (
        f"📹 *{title}*\n\n"
        f"👤 Canal: {uploader}\n"
        f"⏱ Duración: {duration}\n\n"
        "Selecciona el formato de descarga:"
    )

    # Botones de selección de formato
    keyboard = [
        [
            InlineKeyboardButton("🎬 Video", callback_data="format_video"),
            InlineKeyboardButton("🎵 Audio MP3", callback_data="format_audio")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Enviar thumbnail si está disponible
    thumbnail = info.get('thumbnail')
    if thumbnail:
        try:
            await status_msg.delete()
            await update.message.reply_photo(
                photo=thumbnail,
                caption=info_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        except:
            await status_msg.edit_text(info_text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await status_msg.edit_text(info_text, reply_markup=reply_markup, parse_mode='Markdown')


async def format_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja la selección de formato"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    format_type = query.data.replace("format_", "")

    if user_id not in user_urls:
        await query.edit_message_text("❌ Sesión expirada. Envía el enlace nuevamente.")
        return

    user_urls[user_id]['format'] = format_type

    if format_type == "video":
        # Mostrar opciones de calidad para video
        keyboard = [
            [InlineKeyboardButton("🏆 Mejor calidad", callback_data="quality_best")],
            [InlineKeyboardButton("📺 1080p Full HD", callback_data="quality_1080")],
            [InlineKeyboardButton("📺 720p HD", callback_data="quality_720")],
            [InlineKeyboardButton("📺 480p SD", callback_data="quality_480")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        try:
            await query.edit_message_caption(
                caption="🎬 *Video seleccionado*\n\nElige la calidad:",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        except:
            await query.edit_message_text(
                text="🎬 *Video seleccionado*\n\nElige la calidad:",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
    else:
        # Mostrar opciones de calidad para audio
        keyboard = [
            [InlineKeyboardButton("🔉 Baja (128 kbps)", callback_data="quality_audio_low")],
            [InlineKeyboardButton("🔊 Media (192 kbps)", callback_data="quality_audio_mid")],
            [InlineKeyboardButton("🎧 Alta (320 kbps)", callback_data="quality_audio_high")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        try:
            await query.edit_message_caption(
                caption="🎵 *Audio MP3 seleccionado*\n\nElige la calidad:",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        except:
            await query.edit_message_text(
                text="🎵 *Audio MP3 seleccionado*\n\nElige la calidad:",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )


async def quality_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja la selección de calidad"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    quality = query.data.replace("quality_", "")

    if user_id not in user_urls:
        await query.edit_message_text("❌ Sesión expirada. Envía el enlace nuevamente.")
        return

    user_urls[user_id]['quality'] = quality
    await start_download(update, context)


BAR_WIDTH = 12
SPINNER_FRAMES = ["▰▱▱▱▱", "▰▰▱▱▱", "▰▰▰▱▱", "▰▰▰▰▱", "▰▰▰▰▰"]


def progress_bar(fraction: float, width: int = BAR_WIDTH) -> str:
    """Devuelve una barra tipo ████░░░░ 50%"""
    fraction = max(0.0, min(1.0, fraction or 0.0))
    filled = int(round(fraction * width))
    return "█" * filled + "░" * (width - filled) + f" {int(fraction * 100):3d}%"


def format_bytes(n) -> str:
    """Formatea bytes a KB/MB/GB"""
    if not n:
        return "?"
    n = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{int(n)} B" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


async def update_status(query, text: str):
    """Edita el mensaje de estado (caption si lleva foto, texto si no).
    Ignora errores como 'message is not modified' o límites de Telegram."""
    try:
        await query.edit_message_caption(caption=text)
    except Exception:
        try:
            await query.edit_message_text(text=text)
        except Exception:
            pass


async def start_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicia la descarga del video/audio mostrando el progreso"""
    query = update.callback_query
    user_id = update.effective_user.id

    if user_id not in user_urls:
        return

    user_data = user_urls[user_id]
    url = user_data['url']
    format_type = user_data['format']
    quality = user_data['quality']
    title = user_data['info'].get('title', 'video')[:50]
    chat_id = update.effective_chat.id

    await update_status(query, "⏳ Preparando descarga...")
    phase = "descarga"
    filename = None

    loop = asyncio.get_running_loop()
    progress = {'last': 0.0, 'text': ''}

    def push(text: str, force: bool = False):
        """Se llama desde el hilo de yt-dlp. Programa la edición del mensaje en el
        loop, como mucho una vez cada 2 s para no chocar con los límites de Telegram."""
        now = time.monotonic()
        if text == progress['text']:
            return
        if not force and now - progress['last'] < 2:
            return
        progress['last'] = now
        progress['text'] = text
        asyncio.run_coroutine_threadsafe(update_status(query, text), loop)

    def part_label(d) -> str:
        fmt = d.get('info_dict') or {}
        if format_type == "audio" or fmt.get('vcodec') == 'none':
            return "🎵 audio"
        return "🎬 video"

    def progress_hook(d):
        status = d.get('status')
        if status == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            done = d.get('downloaded_bytes') or 0
            fraction = done / total if total else 0
            lines = [
                f"⬇️ Descargando {part_label(d)}",
                progress_bar(fraction),
                f"{format_bytes(done)} / {format_bytes(total)}",
            ]
            extra = []
            if d.get('speed'):
                extra.append(f"🚀 {format_bytes(d['speed'])}/s")
            if d.get('eta') is not None:
                extra.append(f"⏱ {format_seconds(d['eta'])} restante")
            if extra:
                lines.append("  ·  ".join(extra))
            push("\n".join(lines))
        elif status == 'finished':
            # Cada parte (video, audio) termina por separado: mostrar su barra al 100 %
            total = d.get('total_bytes') or d.get('downloaded_bytes') or 0
            push(
                f"✅ {part_label(d).split(' ', 1)[1].capitalize()} descargado\n"
                f"{progress_bar(1.0)}\n"
                f"{format_bytes(total)} / {format_bytes(total)}",
                force=True,
            )

    def postprocessor_hook(d):
        if d.get('status') != 'started':
            return
        pp = d.get('postprocessor', '')
        if pp == 'ExtractAudio':
            push("🎧 Convirtiendo a MP3...", force=True)
        elif pp == 'Merger':
            push("🎬 Uniendo video y audio...", force=True)

    # Configurar yt-dlp
    output_template = os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s')

    ydl_opts = {
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
        'noprogress': True,
        'progress_hooks': [progress_hook],
        'postprocessor_hooks': [postprocessor_hook],
    }

    if format_type == "audio":
        ydl_opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': AUDIO_QUALITIES.get(quality, '192')
            }]
        })
    else:
        if quality == "best":
            ydl_opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
        else:
            ydl_opts['format'] = f'bestvideo[height<={quality}][ext=mp4]+bestaudio[ext=m4a]/best[height<={quality}][ext=mp4]/best'

    try:
        # Descargar
        def do_download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if format_type == "audio":
                    filename = ydl.prepare_filename(info).rsplit('.', 1)[0] + '.mp3'
                else:
                    filename = ydl.prepare_filename(info)
                return filename, info

        filename, info = await loop.run_in_executor(None, do_download)

        # Verificar que el archivo existe
        if not os.path.exists(filename):
            # Buscar archivo con nombre similar
            base_name = os.path.splitext(os.path.basename(filename))[0]
            for f in os.listdir(DOWNLOAD_DIR):
                if base_name in f:
                    filename = os.path.join(DOWNLOAD_DIR, f)
                    break

        if os.path.exists(filename):
            file_size = os.path.getsize(filename)

            # Telegram tiene límite de 50MB para bots
            if file_size > 50 * 1024 * 1024:
                await update_status(
                    query,
                    f"⚠️ El archivo es muy grande ({file_size // (1024*1024)}MB).\n"
                    "Telegram solo permite archivos hasta 50MB.\n"
                    "Intenta con una calidad menor."
                )
            else:
                # Telegram no informa el avance de la subida, así que mostramos
                # tamaño, un indicador animado y el tiempo transcurrido.
                action = ChatAction.UPLOAD_VIDEO if format_type == "video" else ChatAction.UPLOAD_DOCUMENT

                async def upload_ticker():
                    started = time.monotonic()
                    i = 0
                    while True:
                        try:
                            await context.bot.send_chat_action(chat_id=chat_id, action=action)
                        except Exception:
                            pass
                        elapsed = int(time.monotonic() - started)
                        await update_status(
                            query,
                            f"📤 Subiendo a Telegram ({format_bytes(file_size)})\n"
                            f"{SPINNER_FRAMES[i % len(SPINNER_FRAMES)]}\n"
                            f"⏱ {format_seconds(elapsed)} transcurridos"
                        )
                        i += 1
                        await asyncio.sleep(3)

                phase = "subida"
                ticker = asyncio.create_task(upload_ticker())
                try:
                    with open(filename, 'rb') as f:
                        if format_type == "audio":
                            await context.bot.send_audio(
                                chat_id=chat_id,
                                audio=f,
                                title=title,
                                caption=f"🎵 {title}",
                                read_timeout=MEDIA_UPLOAD_TIMEOUT,
                                write_timeout=MEDIA_UPLOAD_TIMEOUT,
                            )
                        else:
                            await context.bot.send_video(
                                chat_id=chat_id,
                                video=f,
                                caption=f"🎬 {title}",
                                supports_streaming=True,
                                read_timeout=MEDIA_UPLOAD_TIMEOUT,
                                write_timeout=MEDIA_UPLOAD_TIMEOUT,
                            )
                finally:
                    ticker.cancel()

                try:
                    await query.delete_message()
                except Exception:
                    pass

                await context.bot.send_message(
                    chat_id=chat_id,
                    text="✅ ¡Descarga completada! Envía otro enlace para continuar."
                )

        else:
            raise Exception("Archivo no encontrado después de la descarga")

    except TimedOut:
        logger.error(f"Timeout en la fase de {phase}")
        if phase == "subida":
            await update_status(
                query,
                "⚠️ Telegram tardó demasiado en confirmar la subida.\n"
                "Revisa si el archivo llegó al chat; si no, inténtalo de nuevo."
            )
        else:
            await update_status(query, "❌ La descarga tardó demasiado. Inténtalo de nuevo.")

    except Exception as e:
        logger.error(f"Error en {phase}: {e}")
        await update_status(query, f"❌ Error en la {phase}: {str(e)[:100]}")

    finally:
        # Limpiar archivo descargado, haya ido bien o mal
        if filename and os.path.exists(filename):
            try:
                os.remove(filename)
            except Exception:
                pass
        # Limpiar datos del usuario
        user_urls.pop(user_id, None)


def main():
    """Función principal"""
    # Crear aplicación con timeouts amplios (la red puede tardar en responder
    # y el envío de archivos grandes necesita tiempo de escritura)
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(120)
        .pool_timeout(30)
        .get_updates_read_timeout(30)
        .build()
    )

    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))

    # Handler para URLs (mensajes de texto que contengan http)
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'https?://'), handle_url))

    # Handlers para callbacks de botones
    application.add_handler(CallbackQueryHandler(format_callback, pattern=r'^format_'))
    application.add_handler(CallbackQueryHandler(quality_callback, pattern=r'^quality_'))

    # Iniciar bot
    print("Bot iniciado! Presiona Ctrl+C para detener.")
    # bootstrap_retries=-1: reintenta indefinidamente si Telegram no responde al arrancar
    application.run_polling(allowed_updates=Update.ALL_TYPES, bootstrap_retries=-1)


if __name__ == "__main__":
    main()
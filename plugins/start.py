import random
import humanize
from Script import script
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from info import URL, LOG_CHANNEL, SHORTLINK
from urllib.parse import quote_plus
from TechVJ.util.file_properties import get_name, get_media_file_size
from TechVJ.util.human_readable import humanbytes
from database.users_chats_db import db
from utils import temp, get_shortlink
import aiohttp # <--- Kani ku dar haddii uusan horey u jirin


@Client.on_message(filters.command("start") & filters.incoming)
async def start(client, message):
    if not await db.is_user_exist(message.from_user.id):
        await db.add_user(message.from_user.id, message.from_user.first_name)
        await client.send_message(
            LOG_CHANNEL,
            script.LOG_TEXT_P.format(message.from_user.id, message.from_user.mention)
        )

    buttons = [[InlineKeyboardButton("✨ Update Channel", url="https://t.me/vj_botz")]]
    await client.send_message(
        chat_id=message.from_user.id,
        text=script.START_TXT.format(message.from_user.mention, temp.U_NAME, temp.B_NAME),
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=enums.ParseMode.HTML
    )
    return


@Client.on_message(filters.private & (filters.document | filters.video))
async def stream_start(client, message): # <--- Halkan waa inuu ku yaal "async def"
    file = getattr(message, message.media.value)
    filename = file.file_name
    fileid = file.file_id
    username = message.from_user.mention

    # Save the media to LOG CHANNEL
    log_msg = await client.send_cached_media(
        chat_id=LOG_CHANNEL,
        file_id=fileid,
    )

    safe_name = quote_plus(get_name(log_msg))
    msg_id = log_msg.id

    # -----------------------------------------------------------
    #  FIXED HASH — Must match route.py (file_unique_id[:6])
    # -----------------------------------------------------------
    try:
        secure_hash = log_msg.document.file_unique_id[:6]
    except:
        secure_hash = log_msg.video.file_unique_id[:6]

    # -----------------------------------------------------------
    # LINKS
    # -----------------------------------------------------------

    # WATCH → KEEP ORIGINAL TEMPLATE
    watch_link = f"{URL}watch/{msg_id}/{safe_name}?hash={secure_hash}"

    # DOWNLOAD → NOW HLS (.m3u8)
    hls_base_path = f"{URL}hls/{msg_id}/{secure_hash}" 
    download_link = f"{hls_base_path}/index.m3u8" # <-- Kani waa linkiga HLS playlist-ka

    # --- BILOWGA WAXYAABAHA CUSUB EE HAGAAGINAYA ---
    # Waxaan isku dayeynaa inaan bilowno HLS generation-ka isla markaaba
    try:
        await client.send_message(LOG_CHANNEL, f"Starting HLS generation for {msg_id}/{secure_hash}...")
        
        async with aiohttp.ClientSession() as session:
            # Kani wuxuu u dirayaa codsi serverkaaga si uu u bilaabo transcoding-ka
            # Waxaan u malaynaynaa in aad ku darto route-kan cusub route.py
            await session.get(f"{URL}generate/{msg_id}/{secure_hash}") 

        await client.send_message(LOG_CHANNEL, f"HLS generation initiated for {msg_id}/{secure_hash}.")
        
    except Exception as e:
        await client.send_message(LOG_CHANNEL, f"Failed to initiate HLS generation for {msg_id}/{secure_hash}: {e}")
    # --- DHAMMAADKA WAXYAABAHA CUSUB ---


    # Apply shorteners if enabled
    if SHORTLINK:
        watch_link = await get_shortlink(watch_link)
        download_link = await get_shortlink(download_link)

    # Send notification in LOG CHANNEL
    await log_msg.reply_text(
        text=f"•• ɢᴇɴᴇᴇʀᴀᴛᴇᴅ ꜰᴏʀ : {username}\n\n•• ᖴᎥᒪᗴ : {get_name(log_msg)}",
        quote=True,
        disable_web_page_preview=True,
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("🖥 WATCH", url=watch_link),
                    InlineKeyboardButton("📥 DOWNLOAD (HLS)", url=download_link)
                ]
            ]
        )
    )

    # Create reply for user
    buttons = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🖥 WATCH", url=watch_link),
                InlineKeyboardButton("📥 DOWNLOAD (HLS)", url=download_link)
            ]
        ]
    )

    msg_text = (
        f"<i><u>Your Link Generated !</u></i>\n\n"
        f"<b>📂 File :</b> <i>{get_name(log_msg)}</i>\n\n"
        f"<b>📥 DOWNLOAD (HLS):</b> <i>{download_link}</i>\n\n"
        f"<b>🖥 WATCH :</b> <i>{watch_link}</i>\n\n"
        "<b>🔒 Links remain forever until deleted.</b>"
    )

    await message.reply_text(
        text=msg_text,
        quote=True,
        disable_web_page_preview=True,
        reply_markup=buttons
    )

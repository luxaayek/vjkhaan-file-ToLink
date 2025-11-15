import random
import humanize
from Script import script
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from info import URL, LOG_CHANNEL, SHORTLINK
from urllib.parse import quote_plus
from TechVJ.util.file_properties import get_name, get_hash, get_media_file_size
from TechVJ.util.human_readable import humanbytes
from database.users_chats_db import db
from utils import temp, get_shortlink


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
async def stream_start(client, message):

    file = getattr(message, message.media.value)
    filename = file.file_name
    fileid = file.file_id
    username = message.from_user.mention

    # Save file into log channel
    log_msg = await client.send_cached_media(
        chat_id=LOG_CHANNEL,
        file_id=fileid,
    )

    safe_name = quote_plus(get_name(log_msg))
    msg_id = log_msg.id
    secure_hash = get_hash(log_msg)

    # WATCH → keep same (do NOT change)
    watch_link = f"{URL}watch/{msg_id}/{safe_name}?hash={secure_hash}"

    # DOWNLOAD → change to HLS
    download_link = f"{URL}hls/{msg_id}/{secure_hash}/index.m3u8"

    # Apply shortlink if enabled
    if SHORTLINK:
        watch_link = await get_shortlink(watch_link)
        download_link = await get_shortlink(download_link)

    # Send log message
    await log_msg.reply_text(
        text=f"•• Generated link for user {username}\n\n•• File : {get_name(log_msg)}",
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

    # Send final message to user
    reply_markup = InlineKeyboardMarkup(
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
        "<b>🔒 Note: Links never expire until I delete.</b>"
    )

    await message.reply_text(
        text=msg_text,
        quote=True,
        disable_web_page_preview=True,
        reply_markup=reply_markup
    )

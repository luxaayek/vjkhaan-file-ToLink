# start.py (qaybta stream_start)
# ... (code hore) ...

# -----------------------------------------------------------
# LINKS
# -----------------------------------------------------------

# WATCH → KEEP ORIGINAL TEMPLATE
watch_link = f"{URL}watch/{msg_id}/{safe_name}?hash={secure_hash}"

# DOWNLOAD → NOW HLS (.m3u8)
hls_base_path = f"{URL}hls/{msg_id}/{secure_hash}" # Base path for HLS
download_link = f"{hls_base_path}/index.m3u8"

# !!! WAXYAABAHA CUSUB EE HAGAAGINAYA DHIBAATADA !!!
# Isku day inaad abuurto HLS isla markaaba
try:
    # Halkan waxaad u baahan tahay inaad wacdo shaqada transcoding-ka
    # Tusaale: Hadii aad shaqada transcoding-ka ka dhigtay mid si toos ah loo wici karo
    # ama aad serverkaaga u soo dirto codsi HLS-abuur ah
    await client.send_message(LOG_CHANNEL, f"Starting HLS generation for {msg_id}/{secure_hash}...")
    
    # Habka ugu fudud haddii HLS_ROOT uu yahay mid la wadaago (shared) iyo FFmpeg la heli karo:
    # Ama wac endpointka hls_generator via aiohttp client.get(f"{URL}{msg_id}{secure_hash}/generate")
    # Ama si toos ah u fuli run_ffmpeg logic (haddii serverku yahay isla meeshii botku ku yaal)

    # Waan ku siinayaa tusaale ah sida looga wici karo serverkaaga:
    import aiohttp
    async with aiohttp.ClientSession() as session:
        # U wac hls_generator endpoint-ka si uu u abuuro faylasha HLS
        # Note: Tani waxay u baahan tahay in hls_generator endpoint-ka uu jawaabta celiyo 
        # isla markiiba ama uu si async ah u maareeyo transcoding-ka.
        await session.get(f"{URL}{msg_id}{secure_hash}/generate") # U maleynayaa in route.py aad ku darto /generate

    await client.send_message(LOG_CHANNEL, f"HLS generation initiated for {msg_id}/{secure_hash}.")
    
except Exception as e:
    await client.send_message(LOG_CHANNEL, f"Failed to initiate HLS generation for {msg_id}/{secure_hash}: {e}")
# !!! DHAMMAADKA WAXYAABAHA CUSUB !!!

# Apply shorteners if enabled
if SHORTLINK:
    watch_link = await get_shortlink(watch_link)
    download_link = await get_shortlink(download_link)

# ... (code kale) ...

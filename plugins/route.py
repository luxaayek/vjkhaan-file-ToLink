# route.py
# ... (code hore) ...

# Ku dar route gaar ah si aad ugu trigger gareyso HLS generation
@routes.get("/{msg_id:int}{secure_hash:string}/generate", allow_head=True) # Tusaale: /123456abcdef/generate
async def trigger_hls_generation(request: web.Request):
    msg_id = request.match_info["msg_id"]
    secure_hash = request.match_info["secure_hash"]
    
    # Wac qaybta HLS generation ee hls_generator function
    # Waa inaad u sameysaa sidii func gooni ah oo aad wici karto
    return await hls_generator_logic(request, msg_id, secure_hash) # Waxaad u baahan tahay inaad hls_generator u qaybiso laba functions
                                                                # Midda Route-ka ah iyo midda Logic-ga ah

# Kani waa shaqada dhabta ah ee HLS generation (ka soo guuri hls_generator)
async def hls_generator_logic(request, msg_id, secure_hash):
    index = min(work_loads, key=work_loads.get)
    client = multi_clients[index]

    streamer = ByteStreamer(client)
    file_id = await streamer.get_file_properties(msg_id)

    if file_id.unique_id[:6] != secure_hash:
        raise InvalidHash

    folder = f"{HLS_ROOT}/{msg_id}/{secure_hash}"
    os.makedirs(folder, exist_ok=True)

    index_m3u8 = f"{folder}/index.m3u8"

    if os.path.exists(index_m3u8):
        # Already exists, just return path
        return web.Response(text="HLS already generated", content_type="text/plain")

    # Run FFmpeg asynchronously
    process = subprocess.Popen(
        [
            "ffmpeg", "-i", "pipe:0",
            "-c", "copy", # You might want to transcode (e.g., -c:v libx264 -crf 23) if original is not suitable
            "-hls_time", "4",
            "-hls_list_size", "0",
            "-hls_segment_filename", f"{folder}/%03d.ts",
            index_m3u8
        ],
        stdin=subprocess.PIPE
    )

    async for chunk in streamer.yield_file(
        file_id, index, 0, 0, file_id.file_size, 1, 1024 * 1024
    ):
        process.stdin.write(chunk)

    process.stdin.close()
    process.wait()
    
    return web.Response(text="HLS generation complete", content_type="text/plain")


# ... Beddel hls_generator-ka asalka ah si uu u waco hls_generator_logic
@routes.get("/{path:.+}", allow_head=True)
async def hls_generator(request: web.Request):
    try:
        raw_path = request.match_info["path"]
        match = re.search(r"^(\d+)([A-Za-z0-9_-]{6})$", raw_path) # Changed regex for direct msg_id+hash pattern

        if match:
            msg_id = int(match.group(1))
            secure_hash = match.group(2)
        else:
            # If path is not msg_id+hash, try query param for old links
            msg_id = int(re.search(r"(\d+)", raw_path).group(1))
            secure_hash = request.rel_url.query.get("hash")

        return await hls_generator_logic(request, msg_id, secure_hash) # Wac shaqada logic-ga

    except Exception as e:
        logging.error(e)
        raise web.HTTPInternalServerError(text=str(e))

# route.py
# ... (code hore) ...

# ------------ FIXED ROUTE ------------ #
@routes.get("/hls/{msg_id:int}/{secure_hash:string}/index.m3u8", allow_head=True) # Route gaar ah HLS
async def hls_serve(request):
    msg_id = request.match_info["msg_id"]
    secure_hash = request.match_info["secure_hash"]
    
    folder = f"{HLS_ROOT}/{msg_id}/{secure_hash}"
    index_m3u8_path = os.path.join(folder, "index.m3u8")

    if not os.path.exists(index_m3u8_path):
        logging.info(f"HLS index.m3u8 not found for {msg_id}/{secure_hash}. Attempting to generate...")
        try:
            # Call the HLS generation logic
            await hls_generator_logic(request, msg_id, secure_hash) # Tani waa inaad horay u kala qaybisay function-ka
            logging.info(f"HLS generation completed for {msg_id}/{secure_hash}.")
        except Exception as e:
            logging.error(f"Failed to generate HLS for {msg_id}/{secure_hash}: {e}")
            raise web.HTTPInternalServerError(text=f"Failed to generate HLS: {e}")

    return web.FileResponse(index_m3u8_path, mimetype="application/vnd.apple.mpegurl")

@routes.get("/hls/{msg_id:int}/{secure_hash:string}/{filename:.+}", allow_head=True) # Route gaar ah TS segments
async def hls_serve_segments(request):
    msg_id = request.match_info["msg_id"]
    secure_hash = request.match_info["secure_hash"]
    filename = request.match_info["filename"]
    
    file_path = os.path.join(HLS_ROOT, str(msg_id), secure_hash, filename)

    if not os.path.exists(file_path):
        raise web.HTTPNotFound(text="Segment Not Found")

    return web.FileResponse(file_path, mimetype="video/mp2t")

# Kani waa shaqada dhabta ah ee HLS generation, ka soo guuri hls_generator
async def hls_generator_logic(request, msg_id, secure_hash):
    index = min(work_loads, key=work_loads.get)
    client = multi_clients[index]

    streamer = ByteStreamer(client)
    file_id = await streamer.get_file_properties(msg_id)

    if file_id.unique_id[:6] != secure_hash:
        raise InvalidHash # ama web.HTTPForbidden

    folder = f"{HLS_ROOT}/{msg_id}/{secure_hash}"
    os.makedirs(folder, exist_ok=True)

    index_m3u8 = f"{folder}/index.m3u8"

    if os.path.exists(index_m3u8):
        return # Waxaa horey loo abuuray

    logging.info(f"Starting FFmpeg transcoding for {msg_id}/{secure_hash}")
    process = subprocess.Popen(
        [
            "ffmpeg", "-i", "pipe:0",
            "-c", "copy",
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
    logging.info(f"FFmpeg transcoding finished for {msg_id}/{secure_hash}")
    
    # Haddii aad qeybtan u isticmaasho sidii logic-ga ay hls_serve ku waceyso, uma baahnid jawaab web.Response ah.
    # Kaliya ha la dhammeeyo shaqada.

# Ka saar ama beddel hls_generator-ka asalka ah haddii aad Habka 2 isticmaalayso,
# maxaa yeelay route-ka hore ee HLS wuxuu hadda si toos ah u maamuli doonaa abuurista.
# Waa inaad hubisaa inaysan jirin isku dhac routes ah.

# /app/plugins/route.py

# Don't Remove Credit @VJ_Botz
# HLS Streaming Added by ChatGPT

import re, logging, os, asyncio, subprocess
from aiohttp import web # <--- Kani waa inuu halkan ku yaal
from info import *
from TechVJ.bot import multi_clients, work_loads
from TechVJ.server.exceptions import FIleNotFound, InvalidHash
from TechVJ.util.custom_dl import ByteStreamer
from TechVJ.util.render_template import render_page

routes = web.RouteTableDef() # <--- KANI WAA INUU HABA KU YAALO HAWLAHA KALE KA HOR!

HLS_ROOT = "hls"
os.makedirs(HLS_ROOT, exist_ok=True)

@routes.get("/", allow_head=True)
async def root_route_handler(request):
    return web.json_response("HLS StreamBot Running")

@routes.get("/watch/{path:.+}", allow_head=True)
async def watch_handler(request: web.Request):
    try:
        path = request.match_info["path"]
        match = re.search(r"^([A-Za-z0-9_-]{6})(\d+)$", path)

        if match:
            secure_hash = match.group(1)
            msg_id = int(match.group(2))
        else:
            msg_id = int(re.search(r"(\d+)", path).group(1))
            secure_hash = request.rel_url.query.get("hash")

        return web.Response(
            text=await render_page(msg_id, secure_hash),
            content_type="text/html"
        )

    except Exception as e:
        logging.error(e)
        raise web.HTTPInternalServerError(text=str(e))

# ------------ HLS GENERATOR LOGIC (SHAQADA DHABTA AH) ------------ #
# Tani waa shaqada HLS-ka dhabta ah, waxaan ka dhignay mid gooni ah
# si loo wici karo meelo kala duwan (sida botka ama route kale)
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
        logging.info(f"HLS index.m3u8 already exists for {msg_id}/{secure_hash}. Skipping generation.")
        return # Waxaa horey loo abuuray, uma baahnid inaad dib u abuurto

    logging.info(f"Starting FFmpeg transcoding for {msg_id}/{secure_hash}")
    process = subprocess.Popen(
        [
            "ffmpeg", "-i", "pipe:0",
            "-c", "copy", # Haddii aad rabto adaptive bitrate, halkan ayaad ka beddeli lahayd
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
    return # Shaqaaddu way dhammaatay

# ------------ HLS GENERATOR API ROUTE (CUSUB) ------------ #
# Kani waa route cusub oo botku wici doono si uu u bilaabo HLS generation-ka
@routes.get("/generate/{msg_id:int}/{secure_hash:string}", allow_head=True)
async def hls_generate_api(request: web.Request):
    msg_id = request.match_info["msg_id"]
    secure_hash = request.match_info["secure_hash"]
    try:
        await hls_generator_logic(request, msg_id, secure_hash)
        return web.Response(text="HLS generation initiated/completed.", content_type="text/plain")
    except Exception as e:
        logging.error(f"Error during HLS API generation for {msg_id}/{secure_hash}: {e}")
        raise web.HTTPInternalServerError(text=f"Failed to generate HLS: {e}")

# ------------ HLS SERVING ROUTES (BEDDELKAN MUHIIM AH) ------------ #
# Kani wuxuu bixinayaa HLS playlist-ka (index.m3u8)
@routes.get("/hls/{msg_id:int}/{secure_hash:string}/index.m3u8", allow_head=True)
async def hls_serve_master_playlist(request):
    msg_id = request.match_info["msg_id"]
    secure_hash = request.match_info["secure_hash"]
    
    folder = f"{HLS_ROOT}/{msg_id}/{secure_hash}"
    index_m3u8_path = os.path.join(folder, "index.m3u8")

    if not os.path.exists(index_m3u8_path):
        logging.info(f"HLS index.m3u8 not found for {msg_id}/{secure_hash}. This should not happen if bot initiated generation.")
        # Haddii aad Habka 1 (pre-generate) isticmaalayso, faylkan waa inuu jiraa.
        # Haddii kale, waxaad halkan ugu yeeri kartaa hls_generator_logic, laakiin waxay keenaysaa dib u dhac.
        raise web.HTTPNotFound(text="HLS Playlist Not Found - Generation might have failed or not initiated.")

    return web.FileResponse(index_m3u8_path, mimetype="application/vnd.apple.mpegurl")

# Kani wuxuu bixinayaa qaybaha fiidyowga (Ts segments)
@routes.get("/hls/{msg_id:int}/{secure_hash:string}/{filename:.+}", allow_head=True)
async def hls_serve_segments(request):
    msg_id = request.match_info["msg_id"]
    secure_hash = request.match_info["secure_hash"]
    filename = request.match_info["filename"]
    
    file_path = os.path.join(HLS_ROOT, str(msg_id), secure_hash, filename)

    if not os.path.exists(file_path):
        raise web.HTTPNotFound(text="Segment Not Found")

    return web.FileResponse(file_path, mimetype="video/mp2t") # TS files

# ------------ HLS GENERATOR OLD ROUTE - KA SAAR KANI ------------ #
# Ka saar route-ka hore ee HLS generator-ka (kan hoose)
# Sababtoo ah waxaan hadda leenahay route cusub oo la wici karo `/generate/{msg_id}/{secure_hash}`
# iyo hls_serve_master_playlist oo hubinaya jiritaanka faylka.
# Waa inaad ka saartaa qaybtan si aanay routes-ku isku khilaafin.
# @routes.get("/{path:.+}", allow_head=True)
# async def hls_generator(request: web.Request):
#     ...(waxyaabaha gudihiisa ku jira)

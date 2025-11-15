# HLS StreamBot – Final FIX Version

import re, logging, os, asyncio, subprocess
from aiohttp import web
from info import *
from TechVJ.bot import multi_clients, work_loads
from TechVJ.server.exceptions import FIleNotFound, InvalidHash
from TechVJ.util.custom_dl import ByteStreamer
from TechVJ.util.render_template import render_page

routes = web.RouteTableDef()

HLS_ROOT = "hls"
os.makedirs(HLS_ROOT, exist_ok=True)

@routes.get("/", allow_head=True)
async def root_route_handler(request):
    return web.json_response("HLS StreamBot Running")


# WATCH PAGE
@routes.get("/watch/{path:.+}", allow_head=True)
async def watch_handler(request):
    try:
        path = request.match_info["path"]

        # Extract msg_id & hash
        match = re.match(r"^(\d{1,10})/([A-Za-z0-9_-]{6})$", path)
        if match:
            msg_id = int(match.group(1))
            secure_hash = match.group(2)
        else:
            return web.HTTPNotFound(text="Invalid link format")

        return web.Response(
            text=await render_page(msg_id, secure_hash),
            content_type="text/html"
        )

    except Exception as e:
        logging.error(e)
        raise web.HTTPInternalServerError(text=str(e))


# SERVE HLS FILES
@routes.get("/hls/{path:.+}", allow_head=True)
async def hls_serve(request):
    try:
        full_path = request.match_info["path"]
        file_path = f"{HLS_ROOT}/{full_path}"

        if os.path.exists(file_path):
            return web.FileResponse(file_path)

        raise web.HTTPNotFound(text="Segment Not Found")

    except Exception as e:
        logging.error(e)
        raise web.HTTPInternalServerError(text=str(e))


# MAIN HLS GENERATOR
@routes.get("/{path:.+}", allow_head=True)
async def hls_generator(request):
    try:
        raw_path = request.match_info["path"]

        # Extract msg_id + hash
        match = re.match(r"^(\d{1,10})/([A-Za-z0-9_-]{6})$", raw_path)
        if not match:
            return web.HTTPNotFound(text="Invalid link")

        msg_id = int(match.group(1))
        secure_hash = match.group(2)

        # Load client
        index = min(work_loads, key=work_loads.get)
        client = multi_clients[index]

        streamer = ByteStreamer(client)
        file_id = await streamer.get_file_properties(msg_id)

        # Validate hash
        if file_id.unique_id[:6] != secure_hash:
            raise InvalidHash

        # Folder
        folder = f"{HLS_ROOT}/{msg_id}/{secure_hash}"
        os.makedirs(folder, exist_ok=True)

        index_m3u8 = f"{folder}/index.m3u8"

        # Already generated
        if os.path.exists(index_m3u8):
            return web.Response(
                text=f"/hls/{msg_id}/{secure_hash}/index.m3u8",
                content_type="text/plain"
            )

        # Run FFmpeg
        async def run_ffmpeg():
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

        asyncio.create_task(run_ffmpeg())

        return web.Response(
            text=f"/hls/{msg_id}/{secure_hash}/index.m3u8",
            content_type="text/plain"
        )

    except Exception as e:
        logging.error(e)
        raise web.HTTPInternalServerError(text=str(e))

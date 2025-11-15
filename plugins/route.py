# ------------------------------
#   HLS STREAMBOT – FIXED ROUTES
# ------------------------------

import os
import re
import logging
import asyncio
import subprocess
from aiohttp import web

from info import *
from TechVJ.bot import multi_clients, work_loads
from TechVJ.server.exceptions import InvalidHash
from TechVJ.util.custom_dl import ByteStreamer
from TechVJ.util.render_template import render_page

routes = web.RouteTableDef()

HLS_ROOT = "hls"
os.makedirs(HLS_ROOT, exist_ok=True)


# ROOT CHECK
@routes.get("/", allow_head=True)
async def root_handler(request):
    return web.json_response({"status": "HLS StreamBot Running"})


# --------------------
# WATCH PAGE
# --------------------
@routes.get("/watch/{msg_id:\d+}/{filename}", allow_head=True)
async def watch_handler(request):
    try:
        msg_id = int(request.match_info["msg_id"])
        secure_hash = request.rel_url.query.get("hash")

        if secure_hash is None:
            return web.HTTPNotFound(text="Missing hash!")

        return web.Response(
            text=await render_page(msg_id, secure_hash),
            content_type="text/html"
        )

    except Exception as e:
        logging.error(str(e))
        raise web.HTTPInternalServerError(text=str(e))


# --------------------
# STATIC HLS FILES
# --------------------
@routes.get("/hls/{msg_id:\d+}/{secure_hash}/{filename}", allow_head=True)
async def hls_serve(request):
    try:
        msg_id = request.match_info["msg_id"]
        secure_hash = request.match_info["secure_hash"]
        filename = request.match_info["filename"]

        file_path = f"{HLS_ROOT}/{msg_id}/{secure_hash}/{filename}"

        if os.path.exists(file_path):
            return web.FileResponse(file_path)

        raise web.HTTPNotFound(text="HLS File Not Found")

    except Exception as e:
        logging.error(str(e))
        raise web.HTTPInternalServerError(text=str(e))


# --------------------
# HLS GENERATOR
# --------------------
@routes.get("/{msg_id:\d+}/{secure_hash:[A-Za-z0-9_-]{6}}", allow_head=True)
async def hls_generator(request):
    try:
        msg_id = int(request.match_info["msg_id"])
        secure_hash = request.match_info["secure_hash"]

        # Select client
        index = min(work_loads, key=work_loads.get)
        client = multi_clients[index]

        streamer = ByteStreamer(client)
        file_id = await streamer.get_file_properties(msg_id)

        # Validate hash
        if file_id.unique_id[:6] != secure_hash:
            raise InvalidHash

        folder = f"{HLS_ROOT}/{msg_id}/{secure_hash}"
        os.makedirs(folder, exist_ok=True)

        index_m3u8 = f"{folder}/index.m3u8"

        # If already generated
        if os.path.exists(index_m3u8):
            return web.Response(
                text=f"/hls/{msg_id}/{secure_hash}/index.m3u8",
                content_type="text/plain"
            )

        # GENERATE HLS
        async def run_ffmpeg():
            process = subprocess.Popen(
                [
                    "ffmpeg", "-i", "pipe:0",
                    "-c:v", "copy", "-c:a", "copy",
                    "-hls_time", "4",
                    "-hls_list_size", "0",
                    "-hls_segment_filename", f"{folder}/%03d.ts",
                    index_m3u8
                ],
                stdin=subprocess.PIPE
            )

            async for chunk in streamer.yield_file(
                file_id, index, start=0, end=file_id.file_size,
                block_size=1024 * 1024
            ):
                if chunk:
                    process.stdin.write(chunk)

            process.stdin.close()
            process.wait()

        asyncio.create_task(run_ffmpeg())

        return web.Response(
            text=f"/hls/{msg_id}/{secure_hash}/index.m3u8",
            content_type="text/plain"
        )

    except Exception as e:
        logging.error(str(e))
        raise web.HTTPInternalServerError(text=str(e))

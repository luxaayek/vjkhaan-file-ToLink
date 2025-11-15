# Don't Remove Credit @VJ_Botz
# HLS (Option A – No Re-Encode) Added By ChatGPT For Full Functionality

import re, logging, os, asyncio, subprocess
from aiohttp import web
from aiohttp.http_exceptions import BadStatusLine
from info import *
from TechVJ.bot import multi_clients, work_loads
from TechVJ.server.exceptions import FIleNotFound, InvalidHash
from TechVJ.util.custom_dl import ByteStreamer

routes = web.RouteTableDef()

HLS_ROOT = "hls"
os.makedirs(HLS_ROOT, exist_ok=True)


@routes.get("/", allow_head=True)
async def root_route_handler(request):
    return web.json_response("HLS Enabled StreamBot")


# --------------------------------------------------------------------------
# HLS FILE SERVER  (serves index.m3u8 and .ts files)
# --------------------------------------------------------------------------

@routes.get(r"/hls/{path:\S+}", allow_head=True)
async def hls_serve(request):
    full_path = request.match_info["path"]
    file_path = f"{HLS_ROOT}/{full_path}"

    if os.path.exists(file_path):
        return web.FileResponse(file_path)

    raise web.HTTPNotFound(text="HLS segment not found")


# --------------------------------------------------------------------------
# MAIN STREAM HANDLER — Telegram → FFmpeg → HLS index.m3u8
# --------------------------------------------------------------------------

@routes.get(r"/{path:\S+}", allow_head=True)
async def hls_stream(request: web.Request):
    try:
        raw_path = request.match_info["path"]

        # Extract secure hash & message ID
        match = re.search(r"^([A-Za-z0-9_-]{6})(\d+)$", raw_path)
        if match:
            secure_hash = match.group(1)
            msg_id = int(match.group(2))
        else:
            msg_id = int(re.search(r"(\d+)", raw_path).group(1))
            secure_hash = request.rel_url.query.get("hash")

        # Choose client with lowest workload
        client_index = min(work_loads, key=work_loads.get)
        telegram_client = multi_clients[client_index]

        streamer = ByteStreamer(telegram_client)
        file_id = await streamer.get_file_properties(msg_id)

        # Check hash
        if file_id.unique_id[:6] != secure_hash:
            raise InvalidHash

        # Output folder
        folder = f"{HLS_ROOT}/{msg_id}/{secure_hash}"
        os.makedirs(folder, exist_ok=True)

        index_file = f"{folder}/index.m3u8"

        # Already generated?
        if os.path.exists(index_file):
            return web.Response(
                text=f"/hls/{msg_id}/{secure_hash}/index.m3u8",
                content_type="text/plain"
            )

        # ----------------------------------------------------------------------
        # FFmpeg COPY MODE (NO RE-ENCODE) — FASTEST & SAFE FOR KOYEB
        # ----------------------------------------------------------------------

        async def run_ffmpeg():
            process = subprocess.Popen(
                [
                    "ffmpeg",
                    "-i", "pipe:0",
                    "-c", "copy",
                    "-hls_time", "4",
                    "-hls_list_size", "0",
                    "-hls_segment_filename", f"{folder}/%03d.ts",
                    index_file
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            async for chunk in streamer.yield_file(
                file_id,
                client_index,
                0,
                0,
                file_id.file_size,
                1,
                1024 * 1024
            ):
                process.stdin.write(chunk)

            process.stdin.close()
            process.wait()

        # Run FFmpeg in background (asynchronous)
        asyncio.create_task(run_ffmpeg())

        # Return HLS link immediately (player will wait few seconds)
        return web.Response(
            text=f"/hls/{msg_id}/{secure_hash}/index.m3u8",
            content_type="text/plain"
        )

    except InvalidHash as e:
        raise web.HTTPForbidden(text=e.message)
    except FIleNotFound as e:
        raise web.HTTPNotFound(text=e.message)
    except Exception as e:
        logging.error(str(e))
        raise web.HTTPInternalServerError(text=str(e))

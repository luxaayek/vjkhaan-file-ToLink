# Don't Remove Credit @VJ_Botz
# HLS Streaming Added by ChatGPT (Option A – No Re-Encode)

import re, logging, os, asyncio, subprocess
from aiohttp import web
from aiohttp.http_exceptions import BadStatusLine
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
    return web.json_response("HLS Enabled StreamBot")


# --------------------------------------------------------------------------
# WATCH PAGE (Keep same as your template)
# --------------------------------------------------------------------------

@routes.get(r"/watch/{path:\S+}", allow_head=True)
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
            content_type='text/html'
        )

    except InvalidHash as e:
        raise web.HTTPForbidden(text=e.message)
    except FIleNotFound as e:
        raise web.HTTPNotFound(text=e.message)
    except Exception as e:
        logging.error(str(e))
        raise web.HTTPInternalServerError(text=str(e))



# --------------------------------------------------------------------------
# HLS SERVE ENDPOINT (Serve .ts + index.m3u8)
# --------------------------------------------------------------------------

@routes.get(r"/hls/{path:\S+}", allow_head=True)
async def hls_serve(request):
    try:
        full_path = request.match_info["path"]
        file_path = f"{HLS_ROOT}/{full_path}"

        if os.path.exists(file_path):
            return web.FileResponse(file_path)

        raise web.HTTPNotFound(text="HLS segment missing")

    except Exception as e:
        logging.error(str(e))
        raise web.HTTPInternalServerError(text=str(e))



# --------------------------------------------------------------------------
# MAIN TELEGRAM → FFmpeg → HLS STREAM HANDLER
# --------------------------------------------------------------------------

@routes.get(r"/{path:\S+}", allow_head=True)
async def hls_generator(request: web.Request):
    try:
        raw_path = request.match_info["path"]
        match = re.search(r"^([A-Za-z0-9_-]{6})(\d+)$", raw_path)

        if match:
            secure_hash = match.group(1)
            msg_id = int(match.group(2))
        else:
            msg_id = int(re.search(r"(\d+)", raw_path).group(1))
            secure_hash = request.rel_url.query.get("hash")

        # choose fastest client
        index = min(work_loads, key=work_loads.get)
        client = multi_clients[index]

        streamer = ByteStreamer(client)
        file_id = await streamer.get_file_properties(msg_id)

        # HASH CHECK
        if file_id.unique_id[:6] != secure_hash:
            raise InvalidHash

        # HLS output folder
        folder = f"{HLS_ROOT}/{msg_id}/{secure_hash}"
        os.makedirs(folder, exist_ok=True)

        index_m3u8 = f"{folder}/index.m3u8"

        # Already generated?
        if os.path.exists(index_m3u8):
            return web.Response(
                text=f"/hls/{msg_id}/{secure_hash}/index.m3u8",
                content_type="text/plain"
            )

        # --------------------------------------------------------------
        # RUN FFMPEG (copy mode) NO RE-ENCODE SUPER FAST
        # --------------------------------------------------------------

        async def run_ffmpeg():
            process = subprocess.Popen(
                [
                    "ffmpeg",
                    "-i", "pipe:0",
                    "-c", "copy",
                    "-hls_time", "4",
                    "-hls_list_size", "0",
                    "-hls_segment_filename", f"{folder}/%03d.ts",
                    index_m3u8
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            async for chunk in streamer.yield_file(
                file_id,
                index,
                0,
                0,
                file_id.file_size,
                1,
                1024 * 1024
            ):
                process.stdin.write(chunk)

            process.stdin.close()
            process.wait()

        asyncio.create_task(run_ffmpeg())

        # return HLS URL immediately
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

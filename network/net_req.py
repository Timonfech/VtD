import time
from typing import Optional

import aiohttp


async def fetch(url: str, session: Optional[aiohttp.ClientSession] = None) -> Optional[str]:
    try:
        if session is not None:
            async with session.get(url) as response:
                response.raise_for_status()
                return await response.text()
        else:
            async with aiohttp.ClientSession() as s:
                async with s.get(url) as response:
                    response.raise_for_status()
                    return await response.text()
    except aiohttp.ClientError:
        return None


async def download_file_with_progress(url: str, chunk_size: int = 4096,
                                      session: Optional[aiohttp.ClientSession] = None):
    async def _stream(s: aiohttp.ClientSession):
        async with s.get(url) as response:
            total_size = response.headers.get('content-length')
            total_size = int(total_size) if total_size else None

            downloaded_size = 0
            start_time = time.monotonic()

            async for data in response.content.iter_chunked(chunk_size):
                if isinstance(data, bytes):
                    downloaded_size += len(data)
                    elapsed_time = time.monotonic() - start_time
                    progress = (downloaded_size * 100) / total_size if total_size else None
                    speed_mb_per_s = (downloaded_size / elapsed_time) / 1048576 if elapsed_time > 0 else 0.0
                    yield data, downloaded_size, progress, speed_mb_per_s

    try:
        if session is not None:
            async for chunk in _stream(session):
                yield chunk
        else:
            async with aiohttp.ClientSession() as s:
                async for chunk in _stream(s):
                    yield chunk
    except aiohttp.ClientError:
        return

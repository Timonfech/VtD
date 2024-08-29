import aiohttp
import pytest

from network.net_req import download_file_with_progress


@pytest.mark.asyncio
async def test_download_file_with_progress(aiohttp_client):
    async def mock_handler(request):
        response = b"Test file data" * 10
        return aiohttp.web.Response(body=response)

    app = aiohttp.web.Application()
    app.router.add_get('/mockfile', mock_handler)

    client = await aiohttp_client(app)

    url = client.make_url('/mockfile')
    chunk_size = 1024

    total_downloaded = 0

    async for data, downloaded_size, progress, speed_mb_per_s in download_file_with_progress(url, chunk_size=chunk_size):
        assert isinstance(data, bytes)
        total_downloaded += len(data)
        assert downloaded_size == total_downloaded
        assert speed_mb_per_s >= 0.0

        if progress is not None:
            assert 0 <= progress <= 100

    assert total_downloaded == len(b"Test file data" * 10)

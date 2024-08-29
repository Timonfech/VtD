import asyncio
import json
import pytest
from unittest.mock import MagicMock, AsyncMock

from configs.Configs import Config
from vt_download_logic.vt_processing import VTDownloader


def _make_mock_config() -> Config:
    cfg = MagicMock(spec=Config)
    cfg.vtapi_v2_link = "http://mock.vt.api"
    cfg._api_key = "test_key"
    cfg.key_product = "test_product"
    cfg.malware_destination = "/tmp/test_malware"
    cfg.filtration_conf = MagicMock()
    cfg.av_trust_conf = MagicMock()
    cfg.data_source = MagicMock()
    cfg.vt_batchifier = MagicMock()
    return cfg


@pytest.fixture
def vt_downloader():
    return VTDownloader(_make_mock_config())


@pytest.mark.asyncio
async def test_pause_resume(vt_downloader):
    await vt_downloader.set_pause()
    assert vt_downloader.paused is True

    await vt_downloader.resume()
    assert vt_downloader.paused is False


@pytest.mark.asyncio
async def test_set_stop(vt_downloader):
    await vt_downloader.set_stop()
    assert vt_downloader.stopped is True


@pytest.mark.asyncio
async def test_queue_blocking_on_pause(vt_downloader):
    downloader = vt_downloader
    await downloader.set_pause()

    task = asyncio.create_task(downloader.wait_until_not_paused())

    await asyncio.sleep(0.1)
    assert not task.done()

    await downloader.resume()
    await asyncio.sleep(0.1)
    assert task.done()


@pytest.mark.asyncio
async def test_fetch_from_valid_server(aiohttp_client, vt_downloader):
    from aiohttp import web

    dummy_vt = [{
        "first_seen": "1", "last_seen": "1", "link": "1", "md5": "1",
        "name": "1", "positives": 1, "positives_delta": 1,
        "report": {}, "sha1": "1", "sha256": "1", "size": 1,
        "source_country": "1", "source_id": "1", "ssdeep": "1",
        "tags": [], "timestamp": 1, "total": "1", "type": "1", "vhash": "1"
    }]

    async def valid_handler(request):
        return web.Response(text=json.dumps(dummy_vt))

    app = web.Application()
    app.router.add_get('/valid', valid_handler)
    client = await aiohttp_client(app)

    # Override URL to point at mock server
    vt_downloader._url_with_params = str(client.make_url('/valid'))
    # Low threshold so backpressure never triggers during this test
    vt_downloader.unwritten_files_buffer_count = 1000

    task = asyncio.create_task(vt_downloader.get_vt_info())
    await asyncio.sleep(0.2)

    # Signal stop so get_vt_info exits the loop
    vt_downloader.quit = True
    await task

    # Verify that a parsed batch landed in the queue
    assert vt_downloader.vt_info_lists_queue.qsize() >= 1


@pytest.mark.asyncio
async def test_backpressure_blocks_fetching(aiohttp_client, vt_downloader):
    """get_vt_info must wait while pending_files is above the high-water mark."""
    from aiohttp import web

    async def valid_handler(request):
        return web.Response(text="[]")

    app = web.Application()
    app.router.add_get('/fill', valid_handler)
    client = await aiohttp_client(app)

    vt_downloader._url_with_params = str(client.make_url('/fill'))
    vt_downloader.unwritten_files_buffer_count = 10

    # Fill queue beyond the threshold
    for _ in range(15):
        await vt_downloader.pending_files.put("mock_file")

    task = asyncio.create_task(vt_downloader.get_vt_info())
    await asyncio.sleep(0.15)

    # Queue must still be full — fetching is blocked by backpressure
    assert vt_downloader.pending_files.qsize() == 15

    vt_downloader.quit = True
    await task


@pytest.mark.asyncio
async def test_broken_json(aiohttp_client, vt_downloader):
    from aiohttp import web

    async def broken_json_handler(request):
        return web.Response(text="{invalid json: ")

    app = web.Application()
    app.router.add_get('/broken', broken_json_handler)
    client = await aiohttp_client(app)

    vt_downloader._url_with_params = str(client.make_url('/broken'))

    task = asyncio.create_task(vt_downloader.get_vt_info())
    await asyncio.sleep(0.1)
    vt_downloader.quit = True
    await task

    # Must not crash, and must not enqueue anything
    assert vt_downloader.vt_info_lists_queue.qsize() == 0

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple, Dict, Union, Optional

import aiohttp
from urllib.parse import urlencode

from Entities.FileProcessing import FileProp
from Entities.Vt_inf import VTReportInfo
from configs.Configs import Config
from network import net_req
from vt_download_logic.Filtration import CustomFilter


@dataclass
class DownloaderStats:
    total_vt_bunches: int = 0
    filtered_by_extensions: int = 0
    filtered_by_detection: int = 0
    filtered_by_dumb_score: int = 0
    filtered_by_sha1: int = 0
    saved_files: int = 0
    downloaded_bytes: int = 0
    pending_count: int = 0
    download_progress: Dict[int, Tuple[float, float]] = field(default_factory=dict)
    paused: bool = False
    stopped: bool = False


class VTDownloader:
    MAX_SIZE_BYTES = 25 * 1024 * 1024

    def __init__(self, config: Config, session: Optional[aiohttp.ClientSession] = None):
        self._conf = config
        self._session = session
        self._url_with_params = (
            f"{config.vtapi_v2_link}?{urlencode({'apikey': config._api_key, 'reports': 'true'})}"
        )
        self.custom_filter = CustomFilter(config.filtration_conf, config.av_trust_conf, config.data_source)

        self.statistics_updated_event = asyncio.Event()
        self.pending_files: asyncio.Queue[FileProp] = asyncio.Queue(maxsize=config.max_pending_files)
        self.vt_info_lists_queue: asyncio.Queue[List[VTReportInfo]] = asyncio.Queue(maxsize=config.max_vt_info_lists)
        self.lock = asyncio.Lock()
        self._control = asyncio.Condition()
        self.paused = False
        self.stopped = False
        self.quit = False

        self.unwritten_files_buffer_count = 100
        self.filtered_by_extensions = 0
        self.filtered_by_detection = 0
        self.filtered_by_dumb_score = 0
        self.filtered_by_sha1 = 0
        self.saved_files = 0
        self.total_vt_bunches = 0
        self.downloaded = 0
        self.download_progress: Dict[int, Tuple[float, float]] = {}

    async def set_pause(self):
        async with self._control:
            self.paused = True
            self._control.notify_all()

    async def resume(self):
        async with self._control:
            self.paused = False
            self._control.notify_all()

    async def set_stop(self):
        async with self._control:
            self.stopped = True
            self._control.notify_all()

    async def start_over(self):
        async with self._control:
            self.stopped = False
            self._control.notify_all()

    async def set_quit(self):
        async with self._control:
            self.quit = True
            self._control.notify_all()

    async def wait_until_not_paused(self):
        async with self._control:
            while self.paused:
                await self._control.wait()

    async def wait_until_not_stopped(self):
        async with self._control:
            while self.stopped:
                await self._control.wait()

    async def _update_progress(self, value: Union[int, float, Tuple[int, float, float, float]] = None):
        if value is not None:
            if isinstance(value, tuple):
                async with self.lock:
                    index, downloaded_size, progress, speed_mb_per_s = value
                    if progress == -1.0:
                        del self.download_progress[index]
                    else:
                        self.download_progress[index] = (progress, speed_mb_per_s)
        self.statistics_updated_event.set()

    async def get_progress(self):
        async with self.lock:
            return dict(self.download_progress)

    async def get_stats(self) -> DownloaderStats:
        async with self.lock:
            progress = dict(self.download_progress)
        return DownloaderStats(
            total_vt_bunches=self.total_vt_bunches,
            filtered_by_extensions=self.filtered_by_extensions,
            filtered_by_detection=self.filtered_by_detection,
            filtered_by_dumb_score=self.filtered_by_dumb_score,
            filtered_by_sha1=self.filtered_by_sha1,
            saved_files=self.saved_files,
            downloaded_bytes=self.downloaded,
            pending_count=self.pending_files.qsize(),
            download_progress=progress,
            paused=self.paused,
            stopped=self.stopped,
        )

    async def get_vt_info(self):
        while not self.quit:
            await self.wait_until_not_stopped()
            await self.wait_until_not_paused()

            if self.pending_files.qsize() >= self.unwritten_files_buffer_count:
                while self.pending_files.qsize() > self.unwritten_files_buffer_count // 2:
                    if self.quit:
                        return
                    await asyncio.sleep(0.01)

            vt_response: Optional[str] = await net_req.fetch(self._url_with_params, self._session)
            if vt_response is None:
                continue

            def process_vt_response(response_str: str) -> List[VTReportInfo]:
                try:
                    json_loads = json.loads(response_str)
                    return [VTReportInfo.from_dict(vt_o) for vt_o in json_loads]
                except json.JSONDecodeError:
                    return []

            list_vt_report_infos = await asyncio.to_thread(process_vt_response, vt_response)
            if list_vt_report_infos:
                await self.vt_info_lists_queue.put(list_vt_report_infos)

            self.total_vt_bunches += 1
            asyncio.create_task(self._update_progress())
        return

    async def filter_and_parse(self):
        while not self.quit:
            await self.wait_until_not_stopped()
            await self.wait_until_not_paused()
            new_vt_list = await self.vt_info_lists_queue.get()
            filtered_by_size = [vti for vti in new_vt_list if vti.size <= self.MAX_SIZE_BYTES]

            filtered_by_extensions = self.custom_filter.filter_by_extensions(filtered_by_size)
            self.filtered_by_extensions += len(new_vt_list) - len(filtered_by_extensions)
            asyncio.create_task(self._update_progress())

            filtered_by_detection = self.custom_filter.exclude_provider_detections(
                filtered_by_extensions, self._conf.excluded_provider
            )
            self.filtered_by_detection += len(filtered_by_extensions) - len(filtered_by_detection)
            asyncio.create_task(self._update_progress())

            filtered_by_score = self.custom_filter.weighted_score_filter(
                filtered_by_detection, self._conf.excluded_provider
            )
            self.filtered_by_dumb_score += len(filtered_by_detection) - len(filtered_by_score)
            asyncio.create_task(self._update_progress())

            filtered_by_sha1 = self.custom_filter.filter_by_sha1(filtered_by_score)
            self._conf.data_source.add_all_sha1({o.sha1 for o in filtered_by_sha1})
            self.filtered_by_sha1 += len(filtered_by_score) - len(filtered_by_sha1)
            asyncio.create_task(self._update_progress())

            if filtered_by_sha1:
                for unwritten_f in [
                    FileProp(vt_inf.md5.lower(), vt_inf, Path(self._conf.malware_destination))
                    for vt_inf in filtered_by_sha1
                ]:
                    await self.pending_files.put(unwritten_f)
        return

    async def download_and_save_vt_files(self):
        while not self.quit:
            await self.wait_until_not_stopped()
            unwritten_vt_file = await self.pending_files.get()
            async with self.lock:
                self.saved_files += 1
                file_index = self.saved_files

            async def data_generator():
                downloaded_size = 0
                async for data, downloaded_size, progress, speed_mb_per_s in net_req.download_file_with_progress(
                        unwritten_vt_file.get_link(), session=self._session):
                    asyncio.create_task(
                        self._update_progress((file_index, downloaded_size, progress, speed_mb_per_s)))
                    yield data

                async with self.lock:
                    self.downloaded += downloaded_size

            await self._conf.vt_batchifier.save_files_in_chunks(unwritten_vt_file.get_md5(), data_generator())
            asyncio.create_task(self._update_progress((file_index, 0.0, -1.0, 0.0)))
        return

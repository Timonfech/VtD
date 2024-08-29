import asyncio
import curses

import aiohttp

from cli.facade import VTDownloaderCLI
from configs.Configs import set_up_config
from vt_download_logic.vt_processing import VTDownloader


async def main(screen):
    config = set_up_config()

    async with aiohttp.ClientSession() as session:
        downloader = VTDownloader(config, session=session)
        cli = VTDownloaderCLI(screen, downloader)

        cli_task = asyncio.create_task(cli.run())
        vt_info_task = asyncio.create_task(downloader.get_vt_info())
        filter_and_parse_task = asyncio.create_task(downloader.filter_and_parse())
        download_tasks = [
            asyncio.create_task(downloader.download_and_save_vt_files())
            for _ in range(8)
        ]

        await asyncio.gather(cli_task, vt_info_task, filter_and_parse_task, *download_tasks)


def wrapper(screen):
    asyncio.run(main(screen))


if __name__ == "__main__":
    curses.wrapper(wrapper)

import asyncio
import curses
import math

from vt_download_logic.vt_processing import VTDownloader, DownloaderStats


def _humanize_bytes(size_bytes: int) -> str:
    if size_bytes == 0:
        return "0 B"
    units = ("B", "KB", "MB", "GB", "TB")
    i = min(int(math.floor(math.log(max(size_bytes, 1), 1024))), len(units) - 1)
    return f"{size_bytes / math.pow(1024, i):.2f} {units[i]}"


class VTDownloaderCLI:
    def __init__(self, screen: curses.window, downloader: VTDownloader):
        self.screen = screen
        self.height, self.width = screen.getmaxyx()
        self.downloader = downloader
        self.paused = False
        self.stopped = False
        self.quit = False
        curses.curs_set(0)
        self.screen.nodelay(True)

    # ── Safe bounded write ────────────────────────────────────────

    def _w(self, row: int, col: int, text: str, max_w: int, attr: int = curses.A_NORMAL):
        if row < 0 or row >= self.height or col < 0 or col >= self.width:
            return
        avail = min(max_w, self.width - col - 1)
        if avail <= 0:
            return
        try:
            self.screen.addstr(row, col, text[:avail], attr)
        except curses.error:
            pass

    # ── Layout rendering ──────────────────────────────────────────

    def _draw_status_bar(self, stats: DownloaderStats):
        if stats.paused:
            indicator = "[ PAUSED  ]"
        elif stats.stopped:
            indicator = "[ STOPPED ]"
        else:
            indicator = "[ RUNNING ]"
        hints = "[p] pause  [s] stop  [q] quit"
        line = f" {indicator}    {hints}"
        self._w(0, 0, line.ljust(self.width - 1), self.width - 1,
                curses.A_BOLD | curses.A_REVERSE)

    def _draw_divider(self):
        mid = self.width // 2
        for r in range(1, self.height):
            self._w(r, mid, "\u2502", 1)  # │

    def _draw_stats_panel(self, stats: DownloaderStats):
        mid = self.width // 2
        pw = mid - 2

        rows = [
            ("PIPELINE STATISTICS",       None),
            ("",                          None),
            ("VT batches fetched",        stats.total_vt_bunches),
            ("Filtered  (ext)",           stats.filtered_by_extensions),
            ("Filtered  (detect)",        stats.filtered_by_detection),
            ("Filtered  (score)",         stats.filtered_by_dumb_score),
            ("Filtered  (sha1)",          stats.filtered_by_sha1),
            ("",                          None),
            ("Pending queue",             stats.pending_count),
            ("Files saved",              stats.saved_files),
            ("Downloaded",               _humanize_bytes(stats.downloaded_bytes)),
        ]

        for offset, (label, value) in enumerate(rows):
            r = 1 + offset
            if r >= self.height:
                break
            if value is None:
                attr = curses.A_BOLD if label else curses.A_NORMAL
                self._w(r, 1, label, pw, attr)
            else:
                self._w(r, 1, f"  {label:<22} {value}", pw)

    def _progress_bar(self, pct: float, speed: float, bar_w: int) -> str:
        bar_w = max(1, bar_w)
        filled = min(int(pct * bar_w / 100), bar_w - 1)
        bar = "=" * filled + ">" + " " * (bar_w - filled - 1)
        return f"{round(pct):3}% [{bar}] {speed:4.1f} MB/s"

    def _draw_downloads_panel(self, stats: DownloaderStats):
        mid = self.width // 2
        col = mid + 1
        pw = self.width - col - 1

        self._w(1, col, "ACTIVE DOWNLOADS", pw, curses.A_BOLD)

        if not stats.download_progress:
            self._w(3, col, "  No active downloads", pw)
            return

        # bar width: panel_w minus  "  #NNN  NNN% [" + "] NN.N MB/s"
        bar_w = max(1, pw - 22)
        for row, (idx, (pct, speed)) in enumerate(sorted(stats.download_progress.items()), start=2):
            if row >= self.height:
                break
            bar = self._progress_bar(pct or 0.0, speed, bar_w)
            self._w(row, col, f"  #{idx:<3} {bar}", pw)

    async def _redraw(self, stats: DownloaderStats):
        self.screen.erase()
        self._draw_status_bar(stats)
        self._draw_divider()
        self._draw_stats_panel(stats)
        self._draw_downloads_panel(stats)
        self.screen.refresh()

    # ── Background loops ──────────────────────────────────────────

    async def _update_info(self):
        """Redraws on each statistics_updated_event, or every 100 ms (for quit)."""
        while not self.quit:
            try:
                await asyncio.wait_for(
                    self.downloader.statistics_updated_event.wait(),
                    timeout=0.1
                )
            except asyncio.TimeoutError:
                continue
            if self.quit:
                break
            self.downloader.statistics_updated_event.clear()
            stats = await self.downloader.get_stats()
            await self._redraw(stats)

    async def _poll_input(self):
        while not self.quit:
            try:
                key = self.screen.getch()
                if key in (ord('q'), ord('\u0439')):          # q / й
                    await self.downloader.set_quit()
                    self.quit = True
                    # Unblock _update_info so it stops within one loop
                    self.downloader.statistics_updated_event.set()
                    return
                elif key in (ord('p'), ord('\u0437')):        # p / з
                    self.paused = not self.paused
                    if self.paused:
                        await self.downloader.set_pause()
                    else:
                        await self.downloader.resume()
                elif key in (ord('s'), ord('\u0456'), ord('\u044b')):   # s / і / ы
                    self.stopped = not self.stopped
                    if self.stopped:
                        await self.downloader.set_stop()
                    else:
                        await self.downloader.start_over()
            except curses.error:
                pass
            await asyncio.sleep(0.05)

    async def _watch_size(self):
        while not self.quit:
            self.height, self.width = self.screen.getmaxyx()
            await asyncio.sleep(1)

    async def _show_quit_screen(self):
        """Clear all panels and show centered goodbye message."""
        self.screen.clear()
        msg = "QUITTING...  GOODBYE!"
        r = self.height // 2
        c = max(0, (self.width - len(msg)) // 2)
        try:
            self.screen.addstr(r, c, msg, curses.A_BOLD)
        except curses.error:
            pass
        self.screen.refresh()
        await asyncio.sleep(1.5)

    async def run(self):
        try:
            await asyncio.gather(
                self._update_info(),
                self._poll_input(),
                self._watch_size(),
            )
        finally:
            await self._show_quit_screen()

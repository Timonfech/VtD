# VTDownloader

VTDownloader is an asynchronous, configurable Python application designed to fetch, parse, filter, and batch volumes of malware metadata and execution reports from VirusTotal. 

It acts as an ingestion pipeline built with defensive programming principles, utilizing Python's `dataclasses` and type hinting (`typing`) to ensure data structure consistency and type safety across the pipeline—from parsing raw JSON responses to saving typed entities into a database.

## Architecture & Async Loop

The application is built for high-throughput data ingestion, separating network I/O from CPU serialization:

* **Event Loop & Concurrency:** Core network communication uses `aiohttp` running concurrently on the `asyncio` event loop.
* **Non-blocking JSON Parsing:** Large JSON bundles from VirusTotal are offloaded to a thread pool via `asyncio.to_thread()`. This decision guarantees that the main event loop is never blocked by CPU-bound JSON serialization, ensuring network sockets remain active.
* **Queue Backpressure:** The system's producers and consumers are connected via bounded `asyncio.Queue` structures (`vt_info_lists_queue` and `pending_files`). Configuration parameters limit the maximum queue sizes. If backend persistence mechanisms (e.g., SQLite DB batching) lag behind network scraping speeds, the queues reach their limits and the native asyncio backpressure suspends producers automatically. This prevents out-of-memory states and holds stable memory consumption.
* **Multi-Signal Filtration:** Entries downloaded from VT are routed through a configurable filter chain:
  1. *Extension Matching* (to ensure files align with targets).
  2. *Provider Exclusion* (ignoring reports from predefined vendors).
  3. *Weighted Score Algorithm* — A normalized 4-signal filter based on trust scores, detection significance, platform consensus, and rising positive trends.
  4. *Target Caching* (cross-checking SQLite DBs using SHA1 metrics to prevent duplicate downloads).

## Terminal User Interface (TUI)

The CLI uses a decoupled `curses` split-panel interface to provide visibility without impacting throughput:
* **Decoupled View Model:** The terminal UI does not directly interact with the business logic. Instead, background ingestion workers asynchronously update a Data Transfer Object (`DownloaderStats` dataclass). The UI reads from this DTO.
* **Layout:** It features a 3-section layout including a static Status Header, a Pipeline Statistics panel showing real-time filter metrics, and an Active Downloads panel.
* **Overflow Protection:** Custom string-rendering bounds and padding routines prevent terminal wrap-around crashes, safely skipping out-of-bounds UI draws instead of halting the ingestion engine.

## Configuration

Duplicate `conf.example.json` to `conf.json`. This JSON configures the engine parameters without modifying code logic: API keys, queue sizes, database paths, AV vendor trust ratings, regex-based file exclusions, and threat significance scores.

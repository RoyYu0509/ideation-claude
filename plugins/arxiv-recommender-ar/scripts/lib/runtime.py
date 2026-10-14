"""Inject config `io.*` operational constants into the low-level client modules.

`apply(cfg)` is called once, automatically, at the end of `config.load_config()`,
so every process that loads the config has its IO knobs sourced from config.yaml
— never from a hidden literal. The client modules start with their knobs set to
None and raise loudly if used before `apply` runs (defensive: e.g. if someone
constructs Config directly and skips load_config).
"""
from __future__ import annotations

from . import arxiv_client, arxiv_oai, quality_signal, s2_client


def apply(cfg) -> None:
    s2_client.API_KEY = cfg.s2_api_key
    s2_client.MIN_INTERVAL_S = cfg.io_s2_min_interval_s
    s2_client.RETRIES = cfg.io_s2_retries
    s2_client.SLEEP_429_S = cfg.io_s2_429_sleep_s
    s2_client.BACKOFF_CAP_S = cfg.io_s2_backoff_cap_s
    s2_client.TIMEOUT_S = cfg.io_s2_timeout
    s2_client.LIMIT_PER_PAGE = cfg.io_s2_limit_per_page
    s2_client.MAX_PAPERS = cfg.io_s2_max_papers
    s2_client.CHUNK_SIZE = cfg.io_s2_chunk_size
    s2_client.REFS_CHUNK_SIZE = cfg.io_s2_refs_chunk_size
    s2_client.TITLE_SEARCH_LIMIT = cfg.io_s2_title_search_limit

    arxiv_client.PAGE_SIZE = cfg.io_arxiv_page_size
    arxiv_client.DELAY_SECONDS = cfg.io_arxiv_delay_seconds
    arxiv_client.NUM_RETRIES = cfg.io_arxiv_num_retries

    arxiv_oai.BASE_URL = cfg.io_arxiv_oai_base_url
    arxiv_oai.TIMEOUT_S = cfg.io_oai_timeout
    arxiv_oai.PAGE_DELAY_S = cfg.io_oai_page_delay_s
    arxiv_oai.MAX_FLOW_CONTROL_WAIT_S = cfg.io_oai_max_flow_control_wait_s
    arxiv_oai.MAX_PAGES = cfg.io_oai_max_pages

    quality_signal.GITHUB_TIMEOUT_S = cfg.io_github_timeout

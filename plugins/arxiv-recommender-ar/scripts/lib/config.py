"""Config + path helpers shared across scripts.

config/config.yaml is the SINGLE SOURCE OF TRUTH for every tunable setting.
There are NO default values in this module: every key is read with `_req`, which
raises ConfigError (naming the key path) if it is absent. A value that is
present but `null` is returned as None — that is a legitimate "feature off" state
for optional keys (e.g. dual_encoder_model), not a missing key. The strict
loader never silently substitutes a hidden default.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class ConfigError(ValueError):
    """Raised when config/config.yaml is missing a required key or holds an
    invalid value. The message always names the offending key path. Subclasses
    ValueError so existing `except ValueError` call sites still catch it."""


def plugin_root() -> Path:
    """Read-only, SHARED plugin code root (specs, config defaults, bin, scripts). Never the
    place for per-instance mutable data — that is data_root()."""
    root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if root:
        return Path(root)
    # When invoked directly (tests, ad-hoc), fall back to walking up from this file.
    here = Path(__file__).resolve()
    return here.parents[2]


def data_root() -> Path:
    """Per-INSTANCE mutable-data root. All generated data (profile, cache, ideations, digests,
    web) lives UNDER here, NOT in the shared plugin dir — so the plugin can run from any
    external folder and two instances stay isolated. Resolves to AR_DATA_ROOT, else
    CLAUDE_PROJECT_DIR (the cwd the session launched from), else plugin_root() as a fallback for
    ad-hoc/test use and for the legacy in-monorepo run (cwd == plugin ⇒ data_root == plugin_root,
    behavior unchanged). In the LIVE pipeline AR_DATA_ROOT is always set — the orchestrator threads it on
    the node path AND bin/run_py.sh defaults it (to CLAUDE_PROJECT_DIR/cwd) for the agent-reproduce path —
    so the plugin_root() fallback below is only ever reached by a direct import (tests/ad-hoc), never by a
    real run, and so cannot silently leak run data into the shared plugin dir."""
    root = os.environ.get("AR_DATA_ROOT") or os.environ.get("CLAUDE_PROJECT_DIR")
    if root:
        return Path(root)
    return plugin_root()


def data_dir() -> Path:
    p = data_root() / "data"
    p.mkdir(parents=True, exist_ok=True)
    return p


def profile_dir() -> Path:
    p = data_dir() / "profile"
    p.mkdir(parents=True, exist_ok=True)
    return p


def cache_dir() -> Path:
    p = data_dir() / "cache"
    p.mkdir(parents=True, exist_ok=True)
    return p


def digest_dir(rel: str = "data/digests") -> Path:
    p = data_root() / rel
    p.mkdir(parents=True, exist_ok=True)
    return p


def web_dir(rel: str = "data/web") -> Path:
    p = data_root() / rel
    p.mkdir(parents=True, exist_ok=True)
    return p


def eval_dir() -> Path:
    p = data_dir() / "eval"
    p.mkdir(parents=True, exist_ok=True)
    return p


def eval_archive_dir() -> Path:
    p = data_dir() / "eval_archive"
    p.mkdir(parents=True, exist_ok=True)
    return p


def profile_dir_for(author_id: str | None = None) -> Path:
    """Return profile dir for a specific author (multi-researcher eval)."""
    if author_id:
        p = data_root() / "data" / "users" / author_id / "profile"
    else:
        p = profile_dir()
    p.mkdir(parents=True, exist_ok=True)
    return p


_MISSING = object()


@dataclass
class Config:
    raw: dict[str, Any]

    # ── Strict accessors (no defaults) ────────────────────────────────────────
    def _req(self, *path: str) -> Any:
        """Return raw[path...]; raise ConfigError naming the full path if any
        segment is absent. A present-but-null value is returned as None."""
        node: Any = self.raw
        for key in path:
            if not isinstance(node, dict) or key not in node:
                full = ".".join(path)
                raise ConfigError(
                    f"config/config.yaml is missing required key '{full}'. "
                    f"Add it to config.yaml (this loader has no default for it)."
                )
            node = node[key]
        return node

    def _req_int(self, *path: str) -> int | None:
        v = self._req(*path)
        return None if v is None else int(v)

    def _req_float(self, *path: str) -> float | None:
        v = self._req(*path)
        return None if v is None else float(v)

    def _req_bool(self, *path: str) -> bool:
        return bool(self._req(*path))

    def _req_str(self, *path: str) -> str | None:
        v = self._req(*path)
        return None if v is None else str(v)

    def _req_choice(self, *path: str, choices: tuple[str, ...]) -> str:
        v = str(self._req(*path))
        if v not in choices:
            full = ".".join(path)
            raise ConfigError(
                f"config/config.yaml key '{full}' is '{v}'; must be one of {choices}."
            )
        return v

    # ── researcher ────────────────────────────────────────────────────────────
    @property
    def s2_author_id(self) -> str | None:
        val = self._req("researcher", "s2_author_id")
        return str(val) if val is not None else None

    @property
    def s2_api_key(self) -> str | None:
        return self._req_str("researcher", "s2_api_key")

    @property
    def personal_website(self) -> str | None:
        return self._req_str("researcher", "personal_website")

    @property
    def google_scholar_url(self) -> str | None:
        return self._req_str("researcher", "google_scholar_url")

    @property
    def arxiv_categories_override(self) -> list[str] | None:
        return self._req("researcher", "arxiv_categories")

    @property
    def arxiv_categories_fixed(self) -> bool:
        return self._req_bool("researcher", "arxiv_categories_fixed")

    @property
    def profile_cutoff(self) -> str | None:
        v = self._req_str("researcher", "profile_cutoff")
        if v is not None:
            from datetime import date
            date.fromisoformat(v)            # ValueError → reported by validate() with the key named
        return v

    @property
    def author_aliases(self) -> list[str]:
        """Extra name forms the researcher publishes under (from config.yaml)."""
        return [str(a) for a in (self._req("researcher", "author_aliases") or [])]

    # ── ingest ────────────────────────────────────────────────────────────────
    @property
    def window_days(self) -> int:
        return int(self._req("ingest", "window_days"))

    @property
    def max_candidates(self) -> int:
        return int(self._req("ingest", "max_candidates"))

    @property
    def cache_fresh_hours(self) -> float:
        return float(self._req("ingest", "cache_fresh_hours"))

    # ── prefetch ──────────────────────────────────────────────────────────────
    @property
    def prefetch_top_k(self) -> int:
        # scout.prefetch_top_k is the single canonical knob (JS workflow + direct use).
        return int(self._req("scout", "prefetch_top_k"))

    @property
    def top_n_papers(self) -> int:
        return int(self._req("scout", "top_n_papers"))

    @property
    def rerank_pass(self) -> str:
        # Phase 3a: 'none' (fused mechanical order → G1 directly; production since 2026-09-19 修订 #12, the
        # pre-registered three-arm test picked R0) | 'a0' (one single-call LLM rerank 300 → 100, the evaluated arm).
        return self._req_choice("scout", "rerank_pass", choices=("none", "a0"))

    @property
    def rerank_return_n(self) -> int:
        # DERIVED — not a config key (2026-07-05 full derivation): the Phase 3.6
        # gate pool is always min(prefetch_top_k, 2*top_n_papers) — backfill
        # headroom for judge rejections, capped by the prefetch pool. 2026-09-19
        # 修订 #11: the G1 -> TOP final select hands the gate exactly 2*top_n papers
        # (was 2*top_n + 1). This property is the formula's ONLY home: bin/cfgval.sh
        # resolves through it and load_config injects it into raw for the JS spec.
        return min(self.prefetch_top_k, 2 * self.top_n_papers)

    @property
    def candidates_per_round(self) -> int:
        return int(self._req("scout", "candidates_per_round"))

    @property
    def ideation_rounds_max(self) -> int:
        return int(self._req("scout", "ideation_rounds_max"))

    @property
    def ideate_brainstorm_count(self) -> int:
        # DERIVED — not a config key (2026-07-11 verified-kill redesign): the
        # generator drafts 2*candidates_per_round + 1 brainstorm candidates
        # before selection. Formula's only home; cfgval.sh resolves through it
        # and load_config injects it into raw.
        return 2 * self.candidates_per_round + 1

    @property
    def embedding_model(self) -> str:
        return str(self._req("prefetch", "embedding_model"))

    @property
    def embedding_backend(self) -> str:
        return self._req_choice("prefetch", "embedding_backend", choices=("local", "hf_api"))

    @property
    def embedding_pooling(self) -> str:
        return self._req_choice("prefetch", "embedding_pooling", choices=("cls", "mean"))

    @property
    def embedding_batch_size(self) -> int:
        return int(self._req("prefetch", "embedding_batch_size"))

    @property
    def oversample_factor(self) -> int:
        return int(self._req("prefetch", "oversample_factor"))

    @property
    def pinned_score_boost(self) -> float:
        return float(self._req("prefetch", "pinned_score_boost"))

    @property
    def empty_profile_query(self) -> str:
        return str(self._req("prefetch", "empty_profile_query"))

    @property
    def bm25_top_k(self) -> int:
        return int(self._req("prefetch", "bm25_top_k"))

    @property
    def use_citation_signal(self) -> bool:
        return self._req_bool("prefetch", "use_citation_signal")

    @property
    def rrf_k(self) -> int:
        return int(self._req("prefetch", "rrf_k"))

    @property
    def use_prf(self) -> bool:
        return self._req_bool("prefetch", "use_prf")

    @property
    def prf_min_year(self) -> int:
        return int(self._req("prefetch", "prf_min_year"))

    @property
    def prf_half_life_months(self) -> float:
        """v2 PRF: a core paper's weight halves every this many months (lib/channel_spec.prf_members)."""
        v = float(self._req("prefetch", "prf_half_life_months"))
        if v <= 0:
            raise ConfigError(f"config/config.yaml key 'prefetch.prf_half_life_months' is {v}; must be > 0.")
        return v

    @property
    def bm25_query(self) -> str:
        """Which phrase list the v2 BM25 channel queries: `extracted` (lib/keyphrases, stored at build time)
        `agent` (the paper notes' grounded keywords) or `agent+extracted` (their union, production's
        default since EVAL-PLAN amendment #9). All three live in every v3 profile."""
        return self._req_choice("prefetch", "bm25_query", choices=("extracted", "agent", "agent+extracted"))

    @property
    def use_dense_channel(self) -> bool:
        """The v2 dense channel: one query over the whole profile (EVAL-PLAN amendment #10)."""
        return self._req_bool("prefetch", "use_dense_channel")

    @property
    def dense_query(self) -> str:
        """What the dense channel encodes: `profile_text` (the recent direction + thread summaries, max
        cosine) or `paper_notes` (each note's "field. method", vectors averaged first)."""
        return self._req_choice("prefetch", "dense_query", choices=("profile_text", "paper_notes"))

    @property
    def use_category_channel(self) -> bool:
        """MB7: the researcher's own arXiv categories as a v2 channel."""
        return self._req_bool("prefetch", "use_category_channel")

    @property
    def use_thread_queries(self) -> bool:
        return self._req_bool("prefetch", "use_thread_queries")

    @property
    def dual_encoder_model(self) -> str | None:
        return self._req_str("prefetch", "dual_encoder_model")

    @property
    def use_category_rebalance(self) -> bool:
        return self._req_bool("prefetch", "use_category_rebalance")

    @property
    def channel_set(self) -> str:
        return self._req_choice("prefetch", "channel_set", choices=("v2", "legacy"))

    @property
    def pool_rule(self) -> str:
        return self._req_choice("prefetch", "pool_rule", choices=("quota", "rrf"))

    @property
    def thread_fusion(self) -> str:
        # choices mirror lib/thread_fusion.MODES (test_thread_fusion pins the two together)
        return self._req_choice("prefetch", "thread_fusion", choices=("per_thread", "split", "sqrt", "best"))

    @property
    def pool_quota_thread_floor(self) -> int:
        return int(self._req("prefetch", "pool_quota", "thread_floor"))

    @property
    def pool_quota_bm25(self) -> int:
        return int(self._req("prefetch", "pool_quota", "bm25"))

    @property
    def pool_quota_citation(self) -> int:
        return int(self._req("prefetch", "pool_quota", "citation"))

    @property
    def citation_direct_weight(self) -> float:
        return float(self._req("prefetch", "citation_direct_weight"))

    @property
    def citation_shared_weight(self) -> float:
        return float(self._req("prefetch", "citation_shared_weight"))

    @property
    def citation_mode(self) -> str:
        return self._req_choice("prefetch", "citation_mode", choices=("coupling", "graph"))

    @property
    def citation_graph_alpha(self) -> float:
        return float(self._req("prefetch", "citation_graph_alpha"))

    @property
    def embedding_cache_stale_days(self) -> int | None:
        return self._req_int("scout", "cache_stale_days")

    # ── output ────────────────────────────────────────────────────────────────
    @property
    def digest_dir_rel(self) -> str:
        return str(self._req("output", "digest_dir"))

    # ── quality signal (STAGED annotate; never enters RRF) ────────────────────
    @property
    def use_quality_signal(self) -> bool:
        return self._req_bool("quality", "use_quality_signal")

    @property
    def quality_use_author_prior(self) -> bool:
        return self._req_bool("quality", "use_author_prior")

    @property
    def quality_use_paper_influence(self) -> bool:
        return self._req_bool("quality", "use_paper_influence")

    @property
    def use_repo_check(self) -> bool:
        return self._req_bool("quality", "use_repo_check")

    @property
    def repo_dead_action(self) -> str:
        return self._req_choice("quality", "repo_dead_action", choices=("flag", "penalize", "filter"))

    @property
    def quality_author_h_strong(self) -> int:
        return int(self._req("quality", "author_h_strong"))

    @property
    def quality_infl_strong(self) -> int:
        return int(self._req("quality", "infl_strong"))

    @property
    def quality_repo_active_min_stars(self) -> int:
        return int(self._req("quality", "repo_active_min_stars"))

    @property
    def quality_cache_stale_days(self) -> int | None:
        return self._req_int("quality", "quality_cache_stale_days")

    @property
    def quality_annotate_scope(self) -> str:
        return self._req_choice("quality", "annotate_scope", choices=("prefetched", "reranked"))

    # ── profile-build / identity verification ─────────────────────────────────
    @property
    def profile_identity_max_papers(self) -> int:
        return int(self._req("profile", "identity_max_papers"))

    @property
    def profile_identity_jaccard(self) -> float:
        return float(self._req("profile", "identity_title_match_jaccard"))

    @property
    def profile_active_window_months(self) -> int:
        return int(self._req("profile", "active_window_months"))

    @property
    def profile_min_threads(self) -> int:
        return int(self._req("profile", "min_threads"))

    @property
    def profile_max_threads(self) -> int:
        return int(self._req("profile", "max_threads"))

    @property
    def profile_md_max_chars(self) -> int:
        return int(self._req("profile", "md_max_chars"))

    @property
    def profile_n_keyphrases(self) -> int:
        """How many retrieval phrases profile_finalize extracts from the own papers (the BM25 query)."""
        return int(self._req("profile", "n_keyphrases"))

    @property
    def profile_category_min_primary(self) -> int:
        return int(self._req("profile", "category_min_primary"))

    @property
    def profile_category_min_cross(self) -> int:
        return int(self._req("profile", "category_min_cross"))

    # ── eval harness (DEV-TIME) ───────────────────────────────────────────────
    @property
    def eval_block(self) -> dict[str, Any]:
        """The whole eval: section (dev-time harness reads sub-keys strictly)."""
        return dict(self._req("eval") or {})

    # ── io (operational constants — timeouts / retries / rate limits) ─────────
    @property
    def io_s2_min_interval_s(self) -> float:
        return float(self._req("io", "s2_min_interval_s"))

    @property
    def io_s2_retries(self) -> int:
        return int(self._req("io", "s2_retries"))

    @property
    def io_s2_429_sleep_s(self) -> float:
        return float(self._req("io", "s2_429_sleep_s"))

    @property
    def io_s2_backoff_cap_s(self) -> float:
        return float(self._req("io", "s2_backoff_cap_s"))

    @property
    def io_s2_timeout(self) -> int:
        return int(self._req("io", "s2_timeout"))

    @property
    def io_s2_limit_per_page(self) -> int:
        return int(self._req("io", "s2_limit_per_page"))

    @property
    def io_s2_max_papers(self) -> int:
        return int(self._req("io", "s2_max_papers"))

    @property
    def io_s2_chunk_size(self) -> int:
        return int(self._req("io", "s2_chunk_size"))

    @property
    def io_s2_refs_chunk_size(self) -> int:
        return int(self._req("io", "s2_refs_chunk_size"))

    @property
    def io_s2_title_search_limit(self) -> int:
        return int(self._req("io", "s2_title_search_limit"))

    @property
    def io_arxiv_page_size(self) -> int:
        return int(self._req("io", "arxiv_page_size"))

    @property
    def io_arxiv_delay_seconds(self) -> int:
        return int(self._req("io", "arxiv_delay_seconds"))

    @property
    def io_arxiv_num_retries(self) -> int:
        return int(self._req("io", "arxiv_num_retries"))

    @property
    def io_ingest_method(self) -> str:
        return self._req_choice("io", "ingest_method", choices=("oai", "api"))

    @property
    def io_arxiv_oai_base_url(self) -> str:
        return str(self._req("io", "arxiv_oai_base_url"))

    @property
    def io_oai_timeout(self) -> int:
        return int(self._req("io", "oai_timeout"))

    @property
    def io_oai_page_delay_s(self) -> float:
        return float(self._req("io", "oai_page_delay_s"))

    @property
    def io_oai_max_flow_control_wait_s(self) -> int:
        return int(self._req("io", "oai_max_flow_control_wait_s"))

    @property
    def io_oai_max_pages(self) -> int:
        return int(self._req("io", "oai_max_pages"))

    @property
    def io_github_timeout(self) -> int:
        return int(self._req("io", "github_timeout"))

    @property
    def io_scholar_base_url(self) -> str:
        return str(self._req("io", "scholar_base_url"))

    @property
    def io_scholar_pagesize(self) -> int:
        return int(self._req("io", "scholar_pagesize"))

    @property
    def io_scholar_timeout(self) -> int:
        return int(self._req("io", "scholar_timeout"))

    # ── Validation ────────────────────────────────────────────────────────────
    def validate(self) -> None:
        """Eagerly touch every property so a missing/invalid key fails fast at
        load time (not lazily mid-run), reporting ALL problems at once."""
        problems: list[str] = []
        for name, member in sorted(vars(type(self)).items()):
            if not isinstance(member, property):
                continue
            try:
                getattr(self, name)
            except ConfigError as e:
                problems.append(str(e))
            except (TypeError, ValueError) as e:
                problems.append(f"key for property '{name}' has an invalid value: {e}")
        if problems:
            raise ConfigError(
                "config/config.yaml failed strict validation:\n  - "
                + "\n  - ".join(sorted(set(problems)))
            )

        # ── Cross-cutting semantic checks ─────────────────────────────────────
        s2_id = self.s2_author_id
        if str(self._req("researcher", "s2_author_id")) == "REPLACE_ME":
            raise ConfigError(
                "researcher.s2_author_id is still REPLACE_ME — set it to your Semantic "
                "Scholar author ID, or set it to null and provide researcher.personal_website."
            )
        if not s2_id and not self.personal_website and not self.google_scholar_url:
            raise ConfigError(
                "config requires researcher.s2_author_id, researcher.personal_website or "
                "researcher.google_scholar_url."
            )
        if self.arxiv_categories_fixed and not self.arxiv_categories_override:
            raise ConfigError(
                "researcher.arxiv_categories_fixed is true but researcher.arxiv_categories is empty."
            )
        for key, v in (("thread_floor", self.pool_quota_thread_floor), ("bm25", self.pool_quota_bm25),
                       ("citation", self.pool_quota_citation)):
            if v < 0:
                raise ConfigError(f"prefetch.pool_quota.{key} must be >= 0, got {v}")
        # (a pool smaller than bm25 + citation seats is legal: pool_select.allocate shrinks those seats)
        if not 1 <= self.profile_min_threads <= self.profile_max_threads:
            raise ConfigError(
                f"profile.min_threads ({self.profile_min_threads}) must be >= 1 and <= "
                f"profile.max_threads ({self.profile_max_threads})"
            )
        if self.profile_active_window_months <= 0 or self.profile_md_max_chars <= 0:
            raise ConfigError("profile.active_window_months and profile.md_max_chars must be > 0")
        if not 1 <= self.io_scholar_pagesize <= 100:
            raise ConfigError(
                f"io.scholar_pagesize must be in [1, 100] (Scholar's page cap; robots.txt forbids "
                f"cstart paging), got {self.io_scholar_pagesize}"
            )
        if self.rrf_k <= 0:
            raise ConfigError(f"prefetch.rrf_k must be > 0, got {self.rrf_k}")
        if not 1 <= self.io_s2_refs_chunk_size <= 100:
            raise ConfigError(f"io.s2_refs_chunk_size must be in [1, 100] (the batch endpoint drops nested "
                              f"references above that — measured 2026-09-12), got {self.io_s2_refs_chunk_size}")
        if not 0.0 < self.citation_graph_alpha < 1.0:
            raise ConfigError(f"prefetch.citation_graph_alpha must be in (0, 1), got {self.citation_graph_alpha}")
        if self.prefetch_top_k < self.top_n_papers:
            raise ConfigError(
                f"scout.prefetch_top_k ({self.prefetch_top_k}) must be >= "
                f"scout.top_n_papers ({self.top_n_papers}) — with the derived gate "
                f"pool rerank_return_n = min(prefetch_top_k, 2*top_n), this single "
                f"check guarantees the whole funnel invariant"
            )
        if self.oversample_factor < 1:
            raise ConfigError(f"prefetch.oversample_factor ({self.oversample_factor}) must be >= 1")


def load_config(path: Path | str | None = None) -> Config:
    if path is None:
        path = plugin_root() / "config" / "config.yaml"
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"Missing {path}. config/config.yaml is the single source of truth and is "
            "tracked in git; restore it or create it with all required keys."
        )
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    if not isinstance(raw, dict):
        raise ConfigError(f"{path} did not parse to a mapping (got {type(raw).__name__}).")
    # ── Per-instance researcher override (data_root/researcher.json) ──────────────────────────
    # Layer the instance's researcher identity over the shared plugin default, so two instances
    # (two external folders) can target two different researchers off ONE shared config.yaml.
    # An instance WITH an override inherits NO identity from the shared default: every researcher.*
    # key the override omits is UNSET (null / [] / false), never the plugin owner's value — before
    # 2026-09-13 an expert's folder silently kept the owner's Scholar page, website and
    # self-exclusion names. Only the credential s2_api_key still comes from the shared config.
    # Absent override — or one with no `researcher` block, e.g. {"use_shared_default": true} from the
    # /auto-research identity card — ⇒ the plugin default (owner) identity, unchanged.
    ov_path = data_root() / "researcher.json"
    if ov_path.exists():
        try:
            ov = json.loads(ov_path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as e:
            raise ConfigError(f"researcher override {ov_path} is not valid JSON: {e}")
        ov_r = ov.get("researcher") if isinstance(ov, dict) else None
        if isinstance(ov_r, dict):
            base_r = raw.get("researcher")
            if not isinstance(base_r, dict):
                raw["researcher"] = base_r = {}
            unset = {"author_aliases": [], "arxiv_categories_fixed": False}
            for k in list(base_r):
                if k != "s2_api_key":                  # a credential, not an identity
                    base_r[k] = unset.get(k)
            base_r.update(ov_r)
    cfg = Config(raw=raw)
    cfg.validate()
    # Inject the DERIVED gate-pool size into the raw dict so raw consumers
    # (workflows/arxiv-scout.js req(), anything reading .raw) see one consistent
    # value without a second copy of the formula.
    raw.setdefault("scout", {})["rerank_return_n"] = cfg.rerank_return_n
    raw["scout"]["ideate_brainstorm_count"] = cfg.ideate_brainstorm_count
    # Push io.* into the low-level client modules so every config consumer gets
    # its timeouts/retries/rate-limits from config.yaml (lazy import avoids any
    # import cycle and keeps config.py importable without the IO deps).
    from . import runtime
    runtime.apply(cfg)
    return cfg

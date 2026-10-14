import sys
from pathlib import Path

import pytest
import yaml

# Repo root is two levels up from skills/tests/; scripts/ lives there.
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

_REAL_CONFIG = REPO_ROOT / "config" / "config.yaml"


@pytest.fixture
def write_config(tmp_path):
    """Factory fixture: write a COMPLETE config to a tmp file, using the real
    tracked config/config.yaml as the base, with optional dotted-key overrides
    and deletions. Returns the path. Used to test the strict (zero-default)
    loader without hand-maintaining a full config dict in every test."""
    def _make(overrides=None, deletions=()):
        cfg = yaml.safe_load(_REAL_CONFIG.read_text(encoding="utf-8"))
        for dotted, val in (overrides or {}).items():
            keys = dotted.split(".")
            node = cfg
            for k in keys[:-1]:
                node = node.setdefault(k, {})
            node[keys[-1]] = val
        for dotted in deletions:
            keys = dotted.split(".")
            node = cfg
            for k in keys[:-1]:
                node = node.get(k, {})
            node.pop(keys[-1], None)
        p = tmp_path / "config.yaml"
        p.write_text(yaml.dump(cfg))
        return p
    return _make

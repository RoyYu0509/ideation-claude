#!/usr/bin/env bash
# validate_github_url.sh <url>
# Exit 0 if the URL is a real, public, non-empty git repo. Exit non-0 otherwise.
set -euo pipefail
url="${1:?usage: $0 <url>}"
timeout 20 git ls-remote --exit-code --quiet "$url" HEAD >/dev/null 2>&1

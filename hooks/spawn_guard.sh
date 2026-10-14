#!/usr/bin/env bash
# auto-research — SPAWN GUARD (PreToolUse hook). Hard-blocks spawning the harness's built-in catch-all
# 'general-purpose' subagent (it carries the Agent tool and would nest into an unbounded spawn tree) and
# redirects the caller to auto-research:leaf-worker. The real logic + the WHY live in the sibling Python file;
# this wrapper just forwards the hook's stdin payload to it.
exec python3 "${BASH_SOURCE%/*}/spawn_guard.py"

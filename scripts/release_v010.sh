#!/usr/bin/env bash
# Compatibility entrypoint; the portable gate owns all checks.
exec python "$(dirname "$0")/release_v010.py" "$@"

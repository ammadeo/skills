#!/usr/bin/env bash
set -eu
python3 "$(dirname "$0")/../../sim/setup.py" incident-open .

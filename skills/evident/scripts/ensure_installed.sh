#!/usr/bin/env sh
# Install the `evident` CLI if it isn't on PATH. Installs Evident itself only; never runs repo code.
set -eu

if command -v evident >/dev/null 2>&1; then
  evident --version
  exit 0
fi

# `evident-map` on PyPI, published from the official repo by trusted publishing.
SOURCE="evident-map"

if command -v uv >/dev/null 2>&1; then
  uv tool install "$SOURCE"
elif command -v pipx >/dev/null 2>&1; then
  pipx install "$SOURCE"
elif command -v python3 >/dev/null 2>&1; then
  python3 -m pip install --user "$SOURCE"
else
  echo "evident needs Python 3.12+ with uv, pipx or pip. See https://github.com/aadilsal/Evident" >&2
  exit 1
fi

evident --version

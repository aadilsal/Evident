# Install the `evident` CLI if it isn't on PATH (Windows). Installs Evident itself only; never runs repo code.
$ErrorActionPreference = 'Stop'

if (Get-Command evident -ErrorAction SilentlyContinue) {
    evident --version
    exit 0
}

# From the official repo until evident-map is published on PyPI (avoids installing a squatted name).
$source = 'git+https://github.com/aadilsal/Evident#subdirectory=engine'

if (Get-Command uv -ErrorAction SilentlyContinue) {
    uv tool install $source
} elseif (Get-Command pipx -ErrorAction SilentlyContinue) {
    pipx install $source
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    py -3 -m pip install --user $source
} else {
    Write-Error 'evident needs Python 3.12+ with uv, pipx or pip. See https://github.com/aadilsal/Evident'
    exit 1
}

evident --version

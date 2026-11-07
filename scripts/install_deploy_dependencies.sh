#!/usr/bin/env bash
# Tek kaynak: Render Blueprint, CI ve desteklenen yerel kurulum.
# Tarihsel requirements.txt araştırma manifestinin hash'ini korur; CANLI için
# requirements-deploy.txt kullanılır. Python 3.12/3.10+ gerektirir.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Build araçlarının bilinen güvenlik düzeltmeleri. Sürümler CI'da da aynıdır;
# değiştirirken PyPI duyurularını ve build/pytest regresyonlarını gözden geçirin.
python -m pip install 'pip==26.2' 'setuptools==84.1.0'
python -m pip install -r requirements-deploy.txt
python -m pip check

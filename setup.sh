#!/usr/bin/env bash
set -euo pipefail

# Setup script replicating Dockerfile for local development

# System packages (pinned versions)
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y --no-install-recommends \
    gdal-bin=3.8.4+dfsg-3ubuntu3 \
    libgdal-dev=3.8.4+dfsg-3ubuntu3 \
    libproj-dev=9.4.0-1build2 \
    proj-data=9.4.0-1build2 \
    build-essential=12.10ubuntu1
apt-get clean
rm -rf /var/lib/apt/lists/*

# Python dependencies via Poetry
pip install --no-cache-dir poetry==1.8.3
poetry config virtualenvs.create false
poetry install --no-interaction --no-root
pip install -e .

# Pre-commit hooks
poetry run pre-commit install

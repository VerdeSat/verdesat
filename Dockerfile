FROM python:3.11-slim

WORKDIR /app

# Copy dependency descriptors first for better build‑cache reuse
COPY pyproject.toml poetry.lock ./

# ---- system & build deps ----
RUN apt-get update -qq && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        gdal-bin libgdal-dev libproj-dev proj-data build-essential && \
    rm -rf /var/lib/apt/lists/*

# ---- Python deps via Poetry ----
RUN pip install --no-cache-dir poetry==1.8.3 && \
    poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-root && \
    pip install -e .

# Copy application source – done *after* deps for cache efficiency
COPY . /app

ENTRYPOINT ["verdesat"]
FROM python:3.10-slim

WORKDIR /app

COPY pyproject.toml ./
# or: COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

ENTRYPOINT ["verdesat"]
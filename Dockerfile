FROM python:3.13-bookworm-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .
ENV NARRATE_HOST=0.0.0.0
ENV NARRATE_PORT=3841
ENV NARRATE_DATA_DIR=/data
ENV NARRATE_LIBRARY_DIR=/library
ENV JELLYFIN_CONTAINER_PATH=/media/audiobooks
ENV TZ=UTC
VOLUME ["/data", "/library"]
EXPOSE 3841
CMD ["narrate", "serve"]

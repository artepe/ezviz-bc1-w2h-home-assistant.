# Isolated recovery of the original BC1 cloud-proxy architecture.
ARG BASE_IMAGE=ghcr.io/home-assistant/aarch64-base:3.22
FROM ${BASE_IMAGE}

ARG BUILD_VERSION=0.1.2
ARG BUILD_ARCH=aarch64
LABEL io.hass.version="${BUILD_VERSION}" \
      io.hass.type="app" \
      io.hass.arch="${BUILD_ARCH}" \
      org.opencontainers.image.source="https://github.com/artepe/ezviz-bc1-w2h-home-assistant."

RUN apk add --no-cache ca-certificates ffmpeg git python3 py3-pip && \
    python3 -m venv /opt/ezviz-venv && \
    /opt/ezviz-venv/bin/pip install --no-cache-dir \
      'git+https://github.com/RenierM26/pyEzvizApi.git@6df75d95a2ee6a68fb71446ee74a55572e2014ea' && \
    apk del git

COPY run.sh /run.sh
COPY runner.py /app/runner.py
RUN chmod 755 /run.sh && chmod 644 /app/runner.py
CMD ["/run.sh"]

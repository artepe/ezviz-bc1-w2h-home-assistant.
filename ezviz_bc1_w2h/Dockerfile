# Experimental Home Assistant OS Raspberry Pi 5 add-on.
# Pinned Alpine v3.22 base and Python package source.
# Workaround for Alpine APKINDEX temporary mirror/network errors seen on Pi 5.
FROM ghcr.io/home-assistant/aarch64-base:3.22

ARG BUILD_VERSION=development
ARG BUILD_ARCH=aarch64
ENV APP_VERSION=${BUILD_VERSION}

LABEL io.hass.version="${BUILD_VERSION}" \
      io.hass.type="app" \
      io.hass.arch="${BUILD_ARCH}" \
      org.opencontainers.image.version="${BUILD_VERSION}" \
      org.opencontainers.image.source="https://github.com/artepe/ezviz-bc1-w2h-home-assistant."

# Some network/DNS configurations intermittently fail to fetch Alpine APKINDEX
# from dl-cdn.alpinelinux.org (apk incorrectly reports "no such package").
# Try several mirrors instead of treating network failure as absent packages.
RUN set -eu; \
    installed=0; \
    for mirror in \
      https://dl-cdn.alpinelinux.org/alpine \
      https://mirror.accum.se/mirror/alpinelinux.org \
      https://mirror.csclub.uwaterloo.ca/alpine \
      https://mirrors.edge.kernel.org/alpine \
    ; do \
      echo "Trying Alpine package mirror: ${mirror}"; \
      printf '%s/v3.22/main\n%s/v3.22/community\n' "${mirror}" "${mirror}" > /etc/apk/repositories; \
      if apk add --no-cache ca-certificates ffmpeg git python3 py3-pip; then \
        installed=1; \
        echo "Alpine package install succeeded from ${mirror}"; \
        break; \
      fi; \
      echo "Failed to install packages from ${mirror}; trying next mirror..."; \
      sleep 3; \
    done; \
    if [ "${installed}" -ne 1 ]; then \
      echo "ERROR: Alpine package mirrors unavailable; check HA Supervisor/container DNS and outbound HTTPS."; \
      exit 1; \
    fi; \
    python3 -m venv /opt/ezviz-venv; \
    /opt/ezviz-venv/bin/pip install --no-cache-dir \
      'git+https://github.com/RenierM26/pyEzvizApi.git@a38ba757a3686cb412cc5029225e2608cdbccc4b'; \
    apk del git

COPY run.sh /run.sh
COPY *.py /app/
COPY static /app/static
RUN chmod 755 /run.sh && chmod 644 /app/*.py

CMD ["/run.sh"]

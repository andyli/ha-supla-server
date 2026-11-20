# SUPLA Server app for Home Assistant.
# One container: MariaDB + SUPLA Cloud (Apache/PHP) + supla-server + supla-scheduler, run by s6-overlay.
# Upstream reference: https://github.com/SUPLA/supla-docker/tree/src (cloud/ and server/).

ARG BUILD_FROM=ghcr.io/home-assistant/base-debian:trixie-2026.11.0

# --- supla-server and supla-scheduler, built on the same Debian release as the runtime ---
FROM ${BUILD_FROM} AS core-build

ARG SUPLA_CORE_VERSION=v26.05

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        g++ gcc git make \
        libcurl4-openssl-dev libmariadb-dev libpq-dev libpqxx-dev libssl-dev nlohmann-json3-dev \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 --recurse-submodules --shallow-submodules \
        --branch "${SUPLA_CORE_VERSION}" https://github.com/SUPLA/supla-core.git /src \
    && make -C /src/supla-scheduler/Release -j"$(nproc)" all \
    && make -C /src/supla-server/Release -j"$(nproc)" all \
    && install -m 0755 /src/supla-server/Release/supla-server /src/supla-scheduler/Release/supla-scheduler /usr/local/bin/

# --- runtime ---
FROM ${BUILD_FROM}

ARG SUPLA_CLOUD_VERSION=26.05.01

ENV S6_CMD_WAIT_FOR_SERVICES_MAXTIME=0 \
    S6_BEHAVIOUR_IF_STAGE2_FAILS=2

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        apache2 libapache2-mod-php8.4 \
        php8.4-cli php8.4-curl php8.4-gd php8.4-intl php8.4-mbstring php8.4-mysql php8.4-opcache \
        php8.4-pgsql php8.4-xml php8.4-zip \
        mariadb-server mariadb-client \
        libcurl4t64 libmariadb3 libpq5 libpqxx-7.10 libssl3t64 \
        openssl \
    && rm -rf /var/lib/apt/lists/* \
    && a2dismod -f mpm_event 2>/dev/null; a2enmod mpm_prefork php8.4 headers rewrite expires deflate ssl alias env \
    && a2dissite 000-default \
    && rm -rf /var/www/html /var/lib/mysql

RUN mkdir -p /var/www/cloud \
    && cd /tmp \
    && curl -fsSLO "https://github.com/SUPLA/supla-cloud/releases/download/v${SUPLA_CLOUD_VERSION}/supla-cloud-v${SUPLA_CLOUD_VERSION}.tar.gz" \
    && curl -fsSLO "https://github.com/SUPLA/supla-cloud/releases/download/v${SUPLA_CLOUD_VERSION}/supla-cloud-v${SUPLA_CLOUD_VERSION}.tar.gz.sha1" \
    && sha1sum -c "supla-cloud-v${SUPLA_CLOUD_VERSION}.tar.gz.sha1" \
    && tar -xzf "supla-cloud-v${SUPLA_CLOUD_VERSION}.tar.gz" -C /var/www/cloud \
    && rm -f supla-cloud-v* \
    && chown -R www-data:www-data /var/www/cloud

COPY --from=core-build /usr/local/bin/supla-server /usr/local/bin/supla-scheduler /usr/local/bin/
COPY rootfs /

RUN a2ensite supla \
    && chmod 0755 /usr/local/bin/supla-* /etc/s6-overlay/scripts/*

LABEL \
    io.hass.type="app" \
    org.opencontainers.image.title="SUPLA Server" \
    org.opencontainers.image.source="https://github.com/andyli/ha-supla-server" \
    org.opencontainers.image.licenses="GPL-2.0-or-later"

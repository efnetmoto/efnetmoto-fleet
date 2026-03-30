# ------ builder ------
FROM alpine:3.23 AS builder

ARG EGGDROP_VERSION=1.10.1

WORKDIR /build

# hadolint ignore=DL3003,DL3018
RUN apk add --no-cache --virtual egg-deps \
    build-base \
    bsd-compat-headers \
    ca-certificates \
    curl \
    gnupg \
    openssl-dev \
    tcl-dev \
    tar \
    zlib-dev \
    && curl -O https://ftp.eggheads.org/pub/eggdrop/source/${EGGDROP_VERSION%.*}/eggdrop-${EGGDROP_VERSION}.tar.gz \
    && curl -O https://ftp.eggheads.org/pub/eggdrop/source/${EGGDROP_VERSION%.*}/eggdrop-${EGGDROP_VERSION}.tar.gz.asc \
    && gpg --batch --keyserver hkps://keyserver.ubuntu.com --recv-key E01C240484DE7DBE190FE141E7667DE1D1A39AFF \
    && gpg --batch --verify eggdrop-${EGGDROP_VERSION}.tar.gz.asc eggdrop-${EGGDROP_VERSION}.tar.gz \
    && gpgconf --kill all \
    && tar -zxvf eggdrop-${EGGDROP_VERSION}.tar.gz \
    && ( cd eggdrop-${EGGDROP_VERSION} \
      && ./configure \
      && make config \
      && make -j"$(nproc)" \
      && make install DEST=/opt/eggdrop ) \
    && rm -rf eggdrop-${EGGDROP_VERSION}

# ------ runtime ------
FROM alpine:3.23

LABEL org.opencontainers.image.authors="Ted Strzalkowski <tedski@efnetmoto.com>" \
      org.opencontainers.image.url="https://github.com/efnetmoto/efnetmoto-fleet"

# hadolint ignore=DL3002,DL3018
RUN apk add --no-cache \
    ca-certificates \
    libstdc++ \
    openssl \
    su-exec \
    tcl \
    zlib

# Copy the eggdrop installation from the builder
# and ensure the volume mount directories exist
COPY --from=builder /opt/eggdrop /eggdrop
# hadolint ignore=SC3009
RUN mkdir -p /eggdrop/data \
    && mkdir -p /eggdrop/logs \
    && mkdir -p /eggdrop/scripts-shared

WORKDIR /eggdrop

COPY entrypoint.sh /entrypoint.sh
RUN chmod 0755 /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]

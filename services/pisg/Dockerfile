FROM alpine:3.19

ENV PISG_VERSION=0.73 \
    STATSGEN_ON_STARTUP=false \
    CRON_SCHEDULE=@hourly

RUN apk add --no-cache \
    perl \
    supercronic \
    tini

RUN apk add --no-cache --virtual build-deps curl && \
    curl -LO https://github.com/PISG/pisg/releases/download/${PISG_VERSION}/pisg-${PISG_VERSION}.tar.gz && \
    mkdir /pisg && \
    tar -xz -C /pisg --strip-components=1 -f pisg-${PISG_VERSION}.tar.gz && \
    chmod +x /pisg/pisg && \
    rm pisg-${PISG_VERSION}.tar.gz && \
    apk del build-deps && \
    adduser -S pisg && \
    mkdir -p /cache /config /logs /output && \
    chown -R pisg:nobody /cache /config /logs /output /pisg

VOLUME /cache /config /logs /output

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

WORKDIR /pisg

USER pisg:nobody

ENTRYPOINT ["/sbin/tini", "--", "/entrypoint.sh"]

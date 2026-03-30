# ------ builder ------
FROM alpine:3.23 AS builder

ARG PISG_VERSION=0.73 

RUN apk add --no-cache \
    curl \
    && curl -LO https://github.com/PISG/pisg/releases/download/${PISG_VERSION}/pisg-${PISG_VERSION}.tar.gz \
    && mkdir /pisg \
    && tar -xz -C /pisg --strip-components=1 -f pisg-${PISG_VERSION}.tar.gz \
    && chmod +x /pisg/pisg 

# ------ runtime -------
FROM alpine:3.23

ENV STATSGEN_ON_STARTUP=false \
    CRON_SCHEDULE=@hourly

RUN apk add --no-cache \
    perl \
    supercronic \
    tini

COPY --from=builder /pisg /pisg

RUN mkdir /cache /config /logs /output 

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

WORKDIR /pisg

ENTRYPOINT ["/sbin/tini", "--", "/entrypoint.sh"]

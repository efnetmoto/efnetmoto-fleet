ARG ALPINE_REF=3.24@sha256:28bd5fe8b56d1bd048e5babf5b10710ebe0bae67db86916198a6eec434943f8b

# ------ builder ------
FROM docker.io/library/alpine:${ALPINE_REF} AS builder

ARG PISG_VERSION=0.73 

RUN apk add --no-cache \
    curl \
    && curl -LO https://github.com/PISG/pisg/releases/download/${PISG_VERSION}/pisg-${PISG_VERSION}.tar.gz \
    && mkdir /pisg \
    && tar -xz -C /pisg --strip-components=1 -f pisg-${PISG_VERSION}.tar.gz \
    && chmod +x /pisg/pisg 

# ------ runtime -------
FROM alpine:${ALPINE_REF}

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

# Minimal ngircd IRC server for the integration tests.
ARG ALPINE_REF=3.24@sha256:28bd5fe8b56d1bd048e5babf5b10710ebe0bae67db86916198a6eec434943f8b

FROM docker.io/library/alpine:${ALPINE_REF}

# hadolint ignore=DL3018
RUN apk add --no-cache ngircd

COPY ngircd.conf /etc/ngircd/ngircd.conf

# ngircd drops to the ngircd user itself (ServerUID in ngircd.conf).
EXPOSE 6667
CMD ["ngircd", "-n", "-f", "/etc/ngircd/ngircd.conf"]

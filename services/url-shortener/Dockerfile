ARG GOLANG_REF=1.25-alpine@sha256:56961d79ea8129efddcc0b8643fd8a5416b4e6228cfd477e3fd61deb2672c587
ARG ALPINE_REF=3.24@sha256:28bd5fe8b56d1bd048e5babf5b10710ebe0bae67db86916198a6eec434943f8b

# ------ builder ------
# modernc.org/sqlite is pure Go, so the build is CGO-free — no C toolchain
# is needed in the builder stage. golang:1.25-alpine is required because
# go.mod declares go 1.25 (modernc.org/sqlite v1.54.0 needs it).
FROM docker.io/librarygolang:${GOLANG_REF} AS builder
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -trimpath -o /url-shortener .

# ------ runtime ------
# alpine:3.23 matches the fleet's pinned alpine version (services/eggdrop,
# services/pisg). The container runs as the host user via docker-compose
# `user:` (see bots/Pompone/docker-compose.yml), mirroring services/pisg —
# no USER/adduser here, so cap_drop: [ALL] needs no exceptions.
FROM docker.io/library/alpine:${ALPINE_REF}

# /data is the bind-mount point for the persistent SQLite database
# (bots/Pompone/url-shortener-data:/data in compose). Creating it here
# documents the volume contract; the bind mount overlays it at runtime.
RUN mkdir -p /data

COPY --from=builder /url-shortener /url-shortener

EXPOSE 8080
# Liveness probe against GET /health. Uses nc + grep (busybox), matching
# the nginx service's healthcheck pattern rather than depending on wget's
# exit-code semantics.
# hadolint ignore=DL3025
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD printf 'GET /health HTTP/1.0\r\nHost: localhost\r\n\r\n' | nc -w3 127.0.0.1 8080 | head -1 | grep -q '200 OK'

ENTRYPOINT ["/url-shortener"]

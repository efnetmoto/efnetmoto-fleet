# url-shortener

A lightweight, self-hosted URL-shortening service for the EFNet Moto fleet.
It provides an authenticated create API for trusted clients (the IRC Search
Bot) and a public redirect endpoint for resolving short URLs. Mappings are
persisted in a SQLite database.

## User/Group Configuration

The container runs as whatever user is specified by the Docker Compose
`user:` directive, matching the host user running the fleet (the same
pattern as `pisg`). This keeps the bind-mounted SQLite database writable
without a `USER` directive in the image or a privilege-drop entrypoint.

## Volumes

- `/data` - Persistent SQLite database (bind-mounted to
  `bots/Pompone/url-shortener-data/` so it is covered by the fleet backup)

## API

| Route | Method | Auth | Purpose |
| --- | --- | --- | --- |
| `/api/v1/links` | POST | Bearer | Create a short URL |
| `/{short_id}` | GET | none | Redirect to the destination (302) |
| `/health` | GET | none | Liveness probe |

### Create

```http
POST /api/v1/links
Authorization: Bearer <API_KEY>
Content-Type: application/json

{"url": "https://example.com/a/long/path"}
```

```http
HTTP/1.1 201 Created
Content-Type: application/json

{"id": "a7K2xP", "url": "https://go.efnetmoto.com/a7K2xP"}
```

### Redirect

```http
GET /a7K2xP
```

```http
HTTP/1.1 302 Found
Location: https://example.com/a/long/path
```

The service never makes outbound requests to the destination URL —
validation is syntactic only (absolute `http`/`https` with a host).

## Configuration

All configuration is via environment variables, loaded once at startup:

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `PORT` | no | `8080` | HTTP listen port |
| `DATABASE_PATH` | yes | — | SQLite database file path |
| `PUBLIC_BASE_URL` | yes | — | Base URL for constructing the returned short URL |
| `API_KEY` | yes | — | Bearer token required by the create API |

Missing required values cause a non-zero exit at startup with a logged
error. The API key is never logged.

## Build

Multi-stage Dockerfile: the builder compiles a CGO-free static binary
(`modernc.org/sqlite` is pure Go), the runtime stage is `alpine:3.23`.

```bash
docker build -t url-shortener services/url-shortener
```

## Usage in docker-compose.yml

The service is deployed as part of the Pompone compose stack; see
`bots/Pompone/docker-compose.yml`. It is not published to the host — the
create API is reachable only on the `pompone-net` Docker network, and the
public redirect endpoint is exposed via a reverse proxy configured in a
gitignored `docker-compose.override.yml` (Traefik labels, cert resolver,
etc. — see `bots/Pompone/docker-compose.override.yml.example`, Example 5).

The compose service deliberately carries no `healthcheck:` block of its
own — the Dockerfile's `HEALTHCHECK` (which actually asserts `200 OK` from
`/health`, not just an open TCP port) is authoritative. Do not add a
weaker compose-level `nc -z` probe; it would shadow the real one.

```yaml
url-shortener:
  build:
    context: ../../services/url-shortener
    dockerfile: Dockerfile
  container_name: pompone-url-shortener
  restart: unless-stopped
  user: "${UID}:${GID}"
  volumes:
    - ./url-shortener-data:/data
  environment:
    - PORT=8080
    - DATABASE_PATH=/data/shortener.db
    - PUBLIC_BASE_URL=https://go.efnetmoto.com
    - API_KEY=${SHORTENER_API_KEY}
  cap_drop:
    - ALL
  security_opt:
    - no-new-privileges:true
```

## Post-deploy verification

Deploy follows the standard Pompone flow (see [DEPLOYMENT.md](../../DEPLOYMENT.md)).
Pompone now requires the Ansible Vault for the shortener API key — set up
`.ansible/vault_pass` and `ansible.cfg` first, then:

```bash
ansible-playbook deploy-pompone.yml --ask-become-pass
```

The public redirect endpoint is not published by the base compose file. Wire
it up by copying Example 5 from `bots/Pompone/docker-compose.override.yml.example`
into a gitignored `docker-compose.override.yml` (Traefik router for
`go.efnetmoto.com`, cert resolver, and the external `traefik-proxy` network),
then redeploy so the override is merged.

Verify the deployed service end-to-end:

```bash
cd bots/Pompone

# 1. The create API is reachable only on pompone-net (no host port). The
#    search bot will call it from inside Pompone's container; verify the
#    same way. <API_KEY> is SHORTENER_API_KEY from bots/Pompone/.env.
docker compose exec pompone wget -qO- \
  --header="Authorization: Bearer <API_KEY>" \
  --header="Content-Type: application/json" \
  --post-data='{"url":"https://www.rust-lang.org/"}' \
  http://url-shortener:8080/api/v1/links
# expect: {"id":"<short_id>","url":"https://go.efnetmoto.com/<short_id>"}

# 2. The public redirect resolves the short id back to the destination.
curl -sI https://go.efnetmoto.com/<short_id>
# expect: HTTP/2 302  Location: https://www.rust-lang.org/

# 3. Health (used by the Dockerfile HEALTHCHECK).
docker compose ps url-shortener   # Status: (healthy)
```

Re-running `deploy-pompone.yml` is safe (idempotent) and preserves existing
links — the SQLite database lives in the bind-mounted
`bots/Pompone/url-shortener-data/` directory, which is included in backups.

## Development

```bash
cd services/url-shortener
go test ./...                 # run all tests
go test -race ./...           # with the race detector
gofmt -l .                    # check formatting
go vet ./...                  # vet
staticcheck ./...             # static analysis
```

CI runs `gofmt`, `go vet`, `staticcheck`, and `go test -race` on changes
under `services/url-shortener/**` (`.github/workflows/go-tests.yml`).

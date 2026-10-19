# Minimal HTTP stub for the external provider APIs used by the integration tests.
# Build context is the repo root so the existing test fixtures can be copied in:
#   docker build -f tests/integration/api-stub/Dockerfile -t efnetmoto/api-stub:integration .
ARG PYTHON_REF=3.12-alpine@sha256:d09d15e60962ca365d1cd544a48773bac9d33f2fb1b00f2aa0deec78ade7dc31

FROM docker.io/library/python:${PYTHON_REF}

WORKDIR /app
COPY tests/integration/api-stub/server.py /app/server.py
COPY shared/python-scripts/tests/searchbot/fixtures /fixtures/searchbot
COPY shared/python-scripts/tests/weather/fixtures /fixtures/weather

ENV INTEGRATION_FIXTURES=/fixtures

EXPOSE 8080
CMD ["python3", "/app/server.py"]

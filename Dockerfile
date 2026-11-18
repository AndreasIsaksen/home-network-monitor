FROM python:3.13-slim-bookworm AS base

ARG SPEEDTEST_VERSION=1.2.0
ARG TARGETARCH

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl iproute2 iputils-ping iw \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

RUN set -eux; \
    case "${TARGETARCH:-amd64}" in \
      amd64) speedtest_arch=x86_64 ;; \
      arm64) speedtest_arch=aarch64 ;; \
      *) echo "Unsupported architecture: ${TARGETARCH}" >&2; exit 1 ;; \
    esac; \
    curl -fsSL "https://install.speedtest.net/app/cli/ookla-speedtest-${SPEEDTEST_VERSION}-linux-${speedtest_arch}.tgz" -o /tmp/speedtest.tgz; \
    tar -xzf /tmp/speedtest.tgz -C /usr/local/bin speedtest; \
    chmod 0755 /usr/local/bin/speedtest; \
    rm /tmp/speedtest.tgz

COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir --no-deps .

FROM base AS test
COPY requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY tests ./tests
RUN pytest -q

FROM base AS runtime
ENTRYPOINT ["netwatch"]
CMD ["run"]

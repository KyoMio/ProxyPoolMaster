FROM node:20-bookworm-slim AS frontend-builder

ARG APP_RELEASE_VERSION=""
ARG APP_GIT_SHA=""

WORKDIR /build/web-ui

ENV APP_RELEASE_VERSION=${APP_RELEASE_VERSION} \
    APP_GIT_SHA=${APP_GIT_SHA}

COPY web-ui/package.json web-ui/package-lock.json ./
RUN npm ci

COPY web-ui/ ./
RUN npm run build

FROM python:3.11-slim-bookworm AS python-deps

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build/python

COPY requirements.txt ./
RUN pip install --prefix=/install -r requirements.txt

FROM python:3.11-slim-bookworm

ARG APP_RELEASE_VERSION=""
ARG APP_GIT_SHA=""
ARG APP_IMAGE_TAG=""

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FASTAPI_HOST=0.0.0.0 \
    FASTAPI_PORT=8000 \
    NGINX_PORT=8080 \
    CONFIG_FILE=/app/data/config/config.json \
    APP_RELEASE_VERSION=${APP_RELEASE_VERSION} \
    APP_GIT_SHA=${APP_GIT_SHA} \
    APP_IMAGE_TAG=${APP_IMAGE_TAG}

WORKDIR /app

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends nginx wget tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && rm -f /etc/nginx/sites-enabled/default \
    && mkdir -p /app/logs /app/web-ui /app/data/custom_collectors /app/data/config /var/cache/nginx

COPY --from=python-deps /install /usr/local

COPY src ./src
COPY main.py ./main.py
COPY config.default.json ./config.default.json
COPY requirements.txt ./requirements.txt
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
COPY nginx.conf /etc/nginx/conf.d/proxypool.conf
COPY --from=frontend-builder /build/web-ui/dist ./web-ui/dist

RUN chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 8080

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["app"]

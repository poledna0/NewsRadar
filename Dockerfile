FROM python:3.12-slim

ARG APP_UID=1000
ARG APP_GID=1000

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY config.yaml sources.yaml ./
RUN groupadd --gid "${APP_GID}" newsradar \
    && useradd --uid "${APP_UID}" --gid newsradar --no-create-home --shell /usr/sbin/nologin newsradar \
    && mkdir -p /app/data \
    && chown "${APP_UID}:${APP_GID}" /app/data

USER ${APP_UID}:${APP_GID}

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-server-header"]
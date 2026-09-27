# Cloud Run image.
#
# Python 3.12 because google-adk has no wheels for 3.14, which is what this
# machine ships. Slim rather than alpine: thermofeel pulls numpy, and musl
# builds numpy from source.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencies first, so a code change does not reinstall numpy.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY heatline ./heatline

# Cloud Run sends SIGTERM and expects the process to exit, so uvicorn runs as
# PID 1 rather than behind a shell that would swallow the signal.
#
# One worker on purpose. The forecast cache and the rate limiter are both
# per-process, so a second worker in the same container would double the
# effective cap and halve the cache hit rate. Cloud Run scales by container.
ENV PORT=8080
EXPOSE 8080
CMD ["sh", "-c", "exec uvicorn heatline.service:app --host 0.0.0.0 --port ${PORT} --workers 1"]

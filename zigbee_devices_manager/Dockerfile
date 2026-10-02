ARG BUILD_FROM
FROM $BUILD_FROM

RUN apk add --no-cache python3 py3-aiohttp

COPY server.py /app/server.py
COPY web /app/web

CMD ["python3", "/app/server.py"]

FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY *.py /app/
COPY states /app/states
COPY tools /app/tools

RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir .

ENV UPTACAMP_DB_PATH=/data/online_state.db

CMD ["python", "online_api_server.py", "--host", "0.0.0.0", "--port", "8787", "--db", "/data/online_state.db"]

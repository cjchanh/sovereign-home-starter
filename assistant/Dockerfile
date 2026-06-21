FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    SOVEREIGN_HOME_MEMORY_PATH=/state/memory.jsonl

WORKDIR /app
COPY assistant/*.py /app/

RUN useradd --system --uid 10001 --create-home assistant \
    && mkdir -p /state \
    && chown -R assistant:assistant /state /app

USER assistant

CMD ["python3", "assistant.py"]

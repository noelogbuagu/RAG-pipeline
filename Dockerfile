# One image runs both the API (uvicorn) and the UI (streamlit); Compose picks the command.
FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    TIKTOKEN_CACHE_DIR=/opt/tiktoken-cache \
    APP_ENV=production

WORKDIR /app

# Install locked dependencies first so code edits do not invalidate this layer.
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --locked --no-dev --no-install-project

COPY config.py custom_types.py data_loader.py vector_db.py answer_generator.py main.py streamlit_app.py ./

# Download the tokenizer once at build time so chunking needs no start-up download.
RUN python -c "from data_loader import splitter; splitter.split_text('warm up.')"

# Run as an unprivileged user; /app/data is the volume shared by the API and UI.
RUN useradd --system --uid 10001 --home-dir /app app \
    && mkdir -p /app/data/uploads /app/.streamlit \
    && chown -R app:app /app/data /app/.streamlit
USER app

EXPOSE 8000 8501
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]

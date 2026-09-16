FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 UV_COMPILE_BYTECODE=1

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev --no-install-project

COPY src/ src/
RUN uv sync --frozen --no-dev 

COPY artifacts/ artifacts/

EXPOSE 8000
CMD ["uv", "run", "--no-sync", "uvicorn", "my_service.service.app:app", "--host", "0.0.0.0", "--port", "8000"]

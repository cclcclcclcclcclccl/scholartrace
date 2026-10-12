FROM node:24-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/tmp/matplotlib
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 libgl1 libglib2.0-0 fonts-noto-cjk && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements-lock.txt ./
RUN pip install --no-cache-dir -r requirements-lock.txt
COPY backend/ ./backend/
COPY requirements-formula-lock.txt ./
COPY scripts/formula_worker.py ./scripts/formula_worker.py
RUN python -m venv tools/formula-env && tools/formula-env/bin/pip install --no-cache-dir -r requirements-formula-lock.txt
COPY --from=frontend /build/dist ./frontend/dist/
RUN useradd -m -u 10001 scholar && mkdir -p data models && chown -R scholar:scholar /app
USER scholar
EXPOSE 8765
CMD ["python","-m","uvicorn","backend.app:app","--host","0.0.0.0","--port","8765"]

FROM node:22-alpine AS frontend-build

WORKDIR /app/frontend
COPY frontend/package.json ./
RUN npm install
COPY frontend ./
RUN npm run build

FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend /app/backend
RUN pip install --upgrade pip && pip install /app/backend

COPY deploy/entrypoint.sh /app/entrypoint.sh
COPY --from=frontend-build /app/frontend/dist /app/backend/app/static

RUN chmod +x /app/entrypoint.sh

WORKDIR /app/backend
EXPOSE 8000

CMD ["/app/entrypoint.sh"]

# Stage 1: Build frontend
FROM node:20-alpine AS frontend-build
WORKDIR /build/frontend
COPY frontend/package.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Stage 2: Python runtime (plain Alpine, no s6-overlay)
FROM python:3.12-alpine

WORKDIR /app

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./
COPY --from=frontend-build /build/frontend/dist ./static

COPY run.sh /
RUN chmod a+x /run.sh

LABEL \
  io.hass.version="0.4.2" \
  io.hass.type="addon" \
  io.hass.arch="aarch64|amd64"

CMD [ "/run.sh" ]

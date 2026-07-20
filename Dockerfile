# Stage 1: Build the React frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Set up the Python runtime and serve the complete app
FROM python:3.11-slim AS runner
WORKDIR /app

# Install python dependencies
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r ./backend/requirements.txt

# Copy backend files
COPY backend/ ./backend/

# Copy built frontend assets from Stage 1
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Copy demo files and temporary logs for evaluation
COPY demo/ ./demo/

# Copy configuration template / env if present in build context
COPY .env* ./

# Set working directory to backend to match local run environment
WORKDIR /app/backend

# Expose port (FastAPI defaults to 8000, can be overridden by PORT environment variable)
EXPOSE 8000

# Set standard Python environment flags
ENV PORT=8000
ENV PYTHONUNBUFFERED=1
ENV ADMIN_USERNAME=admin
ENV ADMIN_PASSWORD=admin123

# Run the backend server
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT}

# Stage 1: Builder
FROM python:3.13-slim as builder

# Set environment variables for best practices
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
WORKDIR /usr/src/app

# Copy requirements from the source folder
COPY src/requirements.txt .

# Install dependencies into wheels
# This includes all libraries needed for the worker
RUN pip wheel --no-cache-dir --wheel-dir /usr/src/app/wheels -r requirements.txt

# Stage 1: Final Image
FROM python:3.13-slim

# Set environment variables again for the final stage
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Create the standard csbuser
RUN groupadd -r csbuser && useradd --no-log-init -r -g csbuser csbuser

# Set the working directory
WORKDIR /usr/src/app

# Copy dependencies from the builder stage
COPY --from=builder /usr/src/app/wheels /wheels
COPY --from=builder /usr/src/app/requirements.txt .

# Install the dependencies from the pre-built wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt && \
    rm -rf /wheels

# Copy the application source code from the source/ directory
COPY src/ .

# Change the ownership of the application directory to the standard app user
RUN chown -R csbuser:csbuser /usr/src/app

# Switch to the standard app user
USER csbuser

# Gunicorn entrypoint
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "1", "worker:app"]
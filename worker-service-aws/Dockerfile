# --- Stage 1: Builder (Efficient Dependency Install) ---
# Use an official Python runtime as a parent image.
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


# --- Stage 2: Final Image (Security Hardening) ---
FROM python:3.13-slim

# Set environment variables again for the final stage
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Create a dedicated, non-root user for security
RUN groupadd -r csecbridge && useradd --no-log-init -r -g csecbridge csecbridge

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

# Change the ownership of the application directory to the non-root user
RUN chown -R csecbridge:csecbridge /usr/src/app

# Switch to the non-root user (security best practice)
USER csecbridge

# --- Define the command to run the worker ---
# We use Gunicorn to manage the worker process reliably.
# Gunicorn will continuously call the 'app' function in worker.py, which starts
# the infinite BRPOP loop.
# We set 1 worker and 1 thread for a simple, single-threaded consumer.
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "1", "worker:app"]
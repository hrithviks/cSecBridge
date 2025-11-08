# Stage 1 - Builder
FROM python:3.13-slim AS builder

# Set environment variables for the builder stage
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Set the working directory in the container
WORKDIR /usr/src/app

# Install dependencies for the builder stage
COPY src/requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /usr/src/app/wheels -r requirements.txt

# Stage 2 - Application
FROM python:3.13-slim

# Set environment variables again for the final stage
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Create user to run the application
RUN groupadd -r csbuser && useradd --no-log-init -r -g csbuser csbuser

# Set the working directory
WORKDIR /usr/src/app

# Copy dependencies from the builder stage
COPY --from=builder /usr/src/app/wheels /wheels
COPY --from=builder /usr/src/app/requirements.txt .

# Install the dependencies from the pre-built wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt && rm -rf /wheels

# Copy the application source code
COPY src/. .

# Change the ownership of the application directory to the non-root user
RUN chown -R csbuser:csbuser /usr/src/app

# Switch to the non-root user
USER csbuser

# Expose the port 8000 for the application
EXPOSE 8000

# Command to run the application
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--timeout", "120", "run:app"]


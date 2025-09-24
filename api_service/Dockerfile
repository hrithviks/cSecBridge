# Use an official Python runtime as a parent image
FROM python:3.13-slim

# Set the working directory in the container
WORKDIR /usr/src/app

# Copy the requirements file into the container
COPY requirements.txt ./

# Install any needed packages specified in requirements.txt
# Using --no-cache-dir makes the image smaller
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Expose the port the app runs on
EXPOSE 8000

# Define the command to run the application using Gunicorn
# This will be a multi-threaded server suitable for handling concurrent requests
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "run:app"]
# Use a newer version of Ubuntu as the base image
FROM ubuntu:22.04

# Install dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    libgl1-mesa-glx \
    libglib2.0-0

# Specify working directory
WORKDIR /app

# Copy requirements file first (helps with caching)
COPY requirements.txt .

# Create and activate virtual environment
RUN python3 -m venv venv

# Install dependencies within the virtual environment
RUN /bin/bash -c "source venv/bin/activate && pip3 install -r requirements.txt"

# Copy the rest of the application code
COPY . .

# Run main python script
CMD ["venv/bin/python3", "app.py"]

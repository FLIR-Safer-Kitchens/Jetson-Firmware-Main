#!/bin/bash

# Build the Docker image with a tag
sudo docker build -t test_container .
echo ""

# Run the Docker container
sudo docker run --rm -it --name test_container --network=host test_container
echo ""

# Remove all stopped containers (optional)
sudo docker container prune -f
echo ""

# Remove old versions of the image (optional)
sudo docker image prune -f
echo ""

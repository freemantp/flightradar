#!/bin/bash

# Get the short git commit hash
COMMIT_ID=$(git rev-parse --short HEAD)

# Build the Docker image with the commit hash
docker build -t flightradar:latest --build-arg COMMIT_ID=$COMMIT_ID .

echo "Built flightradar:latest with commit ID: $COMMIT_ID"
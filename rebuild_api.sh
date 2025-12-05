#!/bin/bash
# Force rebuild API container to pick up code changes

echo "Stopping API container..."
docker-compose stop api

echo "Removing API container..."
docker-compose rm -f api

echo "Building API container (no cache)..."
docker-compose build --no-cache api

echo "Starting API container..."
docker-compose up -d api

echo "Waiting for API to start..."
sleep 5

echo "Checking API logs for errors..."
docker-compose logs api --tail 50 | grep -i "error\|syntax\|indentation\|started\|uvicorn"


#!/bin/bash

# MedBench Automation Testing Tool - Quick Start Script

echo "🚀 Starting MedBench Automation Testing Tool..."

# Add Node.js to PATH (if needed)
export PATH="/c/Program Files/nodejs:$PATH"

# Navigate to project root
cd "$(dirname "$0")"

echo ""
echo "📦 Step 1: Starting Docker services..."
docker-compose up -d

echo ""
echo "⏳ Waiting for services to initialize (30 seconds)..."
sleep 30

echo ""
echo "🔍 Step 2: Checking service health..."
docker-compose ps

echo ""
echo "🏥 Step 3: Checking API health..."
curl -s http://localhost:8000/api/health | head -5 || echo "API not ready yet"

echo ""
echo "✅ Backend services started!"
echo ""
echo "📋 Next steps:"
echo "   1. Install frontend dependencies (first time only):"
echo "      cd frontend && npm install"
echo ""
echo "   2. Start frontend:"
echo "      cd frontend && npm run dev"
echo ""
echo "   3. Access services:"
echo "      - Frontend: http://localhost:5173"
echo "      - API Docs: http://localhost:8000/api/docs"
echo "      - Grafana: http://localhost:3000"
echo ""
echo "📊 View logs: docker-compose logs -f"
echo "🛑 Stop services: docker-compose down"


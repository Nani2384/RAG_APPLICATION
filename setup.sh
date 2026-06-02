#!/bin/bash

echo "🚀 Setting up Enterprise RAG Application..."

# Create .env from template if it doesn't exist
if [ ! -f .env ]; then
    cp .env.example .env
    echo "✅ Created .env file from template. Please update the API keys (OPENAI_API_KEY)."
fi

echo "📦 Building Docker images..."
docker compose build

echo "✅ Setup complete. Run 'docker compose up' to start the infrastructure."

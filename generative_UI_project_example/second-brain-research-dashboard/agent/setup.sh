#!/bin/bash
# Second Brain Agent - Setup Script

set -e

echo "🧠 Setting up Second Brain Agent..."

# Check if uv is installed
if command -v uv &> /dev/null; then
    echo "✅ uv is installed"

    # Initialize uv project (if not already done)
    if [ ! -f ".python-version" ]; then
        echo "📦 Initializing uv project..."
        uv init --no-workspace
    fi

    # Sync dependencies
    echo "📦 Syncing dependencies with uv..."
    uv sync

    echo "✅ Dependencies installed via uv"
else
    echo "⚠️  uv not found, falling back to pip"

    # Create virtual environment if it doesn't exist
    if [ ! -d ".venv" ]; then
        echo "📦 Creating virtual environment..."
        python3 -m venv .venv
    fi

    # Activate virtual environment
    echo "📦 Activating virtual environment..."
    source .venv/bin/activate

    # Install dependencies
    echo "📦 Installing dependencies with pip..."
    pip install -r requirements.txt

    echo "✅ Dependencies installed via pip"
fi

# Copy .env.example to .env if .env doesn't exist
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file from .env.example..."
    cp .env.example .env
    echo "⚠️  Please edit .env and add your OPENROUTER_API_KEY"
else
    echo "✅ .env file already exists"
fi

echo ""
echo "✨ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env and add your OPENROUTER_API_KEY"
echo "2. Run the agent:"
echo "   - With uv: uv run uvicorn main:app --reload --port 8000"
echo "   - With pip: source .venv/bin/activate && uvicorn main:app --reload --port 8000"
echo "3. Test the health endpoint: curl http://localhost:8000/health"
echo "4. View API docs: http://localhost:8000/docs"

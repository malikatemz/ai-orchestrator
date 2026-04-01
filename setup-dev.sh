#!/bin/bash
# setup-dev.sh - Automated developer setup script

set -e  # Exit on error

echo "🚀 AI Orchestration Platform - Developer Setup"
echo "================================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print status
print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Check prerequisites
echo -e "\n${YELLOW}Checking prerequisites...${NC}"

# Check Python
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 not found. Install from https://python.org"
    exit 1
fi
print_status "Python 3: $(python3 --version)"

# Check Node
if ! command -v node &> /dev/null; then
    print_error "Node.js not found. Install from https://nodejs.org"
    exit 1
fi
print_status "Node.js: $(node --version)"

# Check Docker
if ! command -v docker &> /dev/null; then
    print_warning "Docker not found. Install from https://docker.com"
    print_warning "Skipping Docker Compose setup"
    DOCKER_AVAILABLE=false
else
    print_status "Docker: $(docker --version)"
    DOCKER_AVAILABLE=true
fi

# Check Git
if ! command -v git &> /dev/null; then
    print_error "Git not found. Install from https://git-scm.com"
    exit 1
fi
print_status "Git: $(git --version)"

# Setup environment
echo -e "\n${YELLOW}Setting up environment...${NC}"

if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        print_status "Created .env from .env.example"
        print_warning "⚠ Please add API keys to .env"
    fi
else
    print_status ".env already exists"
fi

# Backend setup
echo -e "\n${YELLOW}Setting up backend...${NC}"

if [ ! -d "backend/venv" ]; then
    cd backend
    python3 -m venv venv
    print_status "Created Python virtual environment"
    
    # Activate venv
    source venv/bin/activate
    
    # Install dependencies
    pip install -q -r requirements.txt
    print_status "Installed Python dependencies"
    
    # Run migrations
    alembic upgrade head
    print_status "Ran database migrations"
    
    cd ..
else
    print_status "Backend venv already exists"
fi

# Frontend setup
echo -e "\n${YELLOW}Setting up frontend...${NC}"

if [ ! -d "frontend/node_modules" ]; then
    cd frontend
    npm install --silent
    print_status "Installed Node.js dependencies"
    cd ..
else
    print_status "Frontend node_modules already exists"
fi

# Create .env.local for frontend if needed
if [ ! -f "frontend/.env.local" ]; then
    cat > frontend/.env.local << EOF
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api
NEXT_PUBLIC_SITE_URL=http://localhost:3000
EOF
    print_status "Created frontend/.env.local"
fi

# Docker Compose setup
if [ "$DOCKER_AVAILABLE" = true ]; then
    echo -e "\n${YELLOW}Setting up Docker Compose...${NC}"
    
    if docker-compose --version &> /dev/null; then
        print_status "Verified docker-compose"
    else
        print_warning "docker-compose not found, trying docker compose"
        if ! docker compose version &> /dev/null; then
            print_error "Neither docker-compose nor docker compose found"
        fi
    fi
fi

# Summary and next steps
echo -e "\n${GREEN}✨ Setup complete!${NC}"
echo -e "\n${YELLOW}Next steps:${NC}"

if [ "$DOCKER_AVAILABLE" = true ]; then
    echo "1. Add API keys to .env file"
    echo "2. Run: docker-compose up -d"
    echo "3. Visit: http://localhost:3000"
    echo ""
    echo "Services will be available at:"
    echo "  API:     http://localhost:8000"
    echo "  Docs:    http://localhost:8000/docs"
    echo "  Frontend: http://localhost:3000"
    echo "  Flower:  http://localhost:5555"
else
    echo "1. Add API keys to .env file"
    echo "2. Start PostgreSQL and Redis manually"
    echo "3. Run backend: cd backend && source venv/bin/activate && uvicorn app.main:app --reload"
    echo "4. Run worker: celery -A app.worker worker --loglevel=info (in another terminal)"
    echo "5. Run frontend: cd frontend && npm run dev (in another terminal)"
fi

echo ""
echo "📖 See GETTING_STARTED.md for detailed onboarding guide"
echo "📚 See DOCUMENTATION_INDEX.md for all documentation"

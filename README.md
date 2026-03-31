# AI Orchestrator MVP

A control layer for AI workflows that prevents failures, adds visibility, and coordinates multiple agents.

## Setup

1. Install Docker and Docker Compose.

2. Clone or navigate to the project directory.

3. Run `docker-compose up --build` to start all services.

4. Access the frontend at http://localhost:3000

5. Backend API at http://localhost:8000

## Services

- **Frontend**: Next.js dashboard
- **Backend**: FastAPI API
- **Worker**: Celery for async tasks
- **Redis**: Queue
- **PostgreSQL**: Database

## Development

To run locally without Docker:

### Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Worker
```bash
cd backend
celery -A app.worker worker --loglevel=info
```

## Deployment

Deploy to Railway, Render, or similar for backend/DB/Redis, and Vercel for frontend.
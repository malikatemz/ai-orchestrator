from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from . import models
from .models import SessionLocal
from .worker import run_task

app = FastAPI(title="AI Orchestrator", version="1.0.0")

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
async def root():
    return {"message": "AI Orchestrator API"}

@app.get("/workflows")
async def get_workflows(db: Session = Depends(get_db)):
    workflows = db.query(models.Workflow).all()
    return {"workflows": [{"id": w.id, "name": w.name, "description": w.description} for w in workflows]}

@app.post("/workflows")
async def create_workflow(workflow: dict, db: Session = Depends(get_db)):
    new_workflow = models.Workflow(name=workflow.get("name"), description=workflow.get("description"))
    db.add(new_workflow)
    db.commit()
    db.refresh(new_workflow)
    return {"id": new_workflow.id, "status": "created"}

@app.get("/workflows/{workflow_id}/tasks")
async def get_tasks(workflow_id: int, db: Session = Depends(get_db)):
    tasks = db.query(models.Task).filter(models.Task.workflow_id == workflow_id).all()
    return {"tasks": [{"id": t.id, "name": t.name, "status": t.status, "retries": t.retries, "output": t.output_data} for t in tasks]}

@app.post("/workflows/{workflow_id}/tasks")
async def create_task(workflow_id: int, task: dict, db: Session = Depends(get_db)):
    new_task = models.Task(workflow_id=workflow_id, name=task.get("name"), input_data=task.get("input"))
    db.add(new_task)
    db.commit()
    db.refresh(new_task)
    # Trigger async task
    run_task.delay(new_task.id)
    return {"id": new_task.id, "status": "queued"}
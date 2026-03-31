from celery import Celery
import os
from .models import SessionLocal, Task

celery = Celery(
    "worker",
    broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.getenv("REDIS_URL", "redis://localhost:6379/0")
)

@celery.task
def run_task(task_id):
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return {"status": "error", "message": "Task not found"}

        task.status = "running"
        db.commit()

        # Simulate task execution
        # Here, integrate with AI APIs like OpenAI
        result = f"Processed input: {task.input_data}"

        task.status = "completed"
        task.output_data = result
        db.commit()

        return {"status": "completed", "result": result}
    except Exception as e:
        task.status = "failed"
        task.retries += 1
        db.commit()
        return {"status": "failed", "error": str(e)}
    finally:
        db.close()
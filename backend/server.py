from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uuid
import os
import json
from pathlib import Path
from backend.orchestrator.graph import run_healing_pipeline
from config.settings import settings
from backend.utils.logger import logger

app = FastAPI(title="Autonomous Healing API", version="1.0.0")

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for dev; restrict in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class HealingRequest(BaseModel):
    repo_path: str
    repo_url: str
    branch_name: str = "main"

# In-memory status tracking (simple implementation)
# In production, use Redis or a database
job_status = {}

def run_agent_task(run_id: str, request: HealingRequest):
    try:
        job_status[run_id] = "RUNNING"
        logger.info(f"Starting job {run_id}")
        
        # Execute the pipeline
        final_state = run_healing_pipeline(
            repo_path=request.repo_path,
            repo_url=request.repo_url,
            run_id=run_id,
            branch_name=request.branch_name
        )
        
        job_status[run_id] = "COMPLETED"
        logger.success(f"Job {run_id} completed successfully")
        
    except Exception as e:
        job_status[run_id] = f"FAILED: {str(e)}"
        logger.error(f"Job {run_id} failed: {e}")

@app.post("/start-healing")
async def start_healing(request: HealingRequest, background_tasks: BackgroundTasks):
    run_id = f"api-run-{uuid.uuid4().hex[:8]}"
    job_status[run_id] = "PENDING"
    
    background_tasks.add_task(run_agent_task, run_id, request)
    
    return {"run_id": run_id, "status": "PENDING", "message": "Healing job submitted"}

@app.get("/status/{run_id}")
async def get_status(run_id: str):
    status = job_status.get(run_id)
    if not status:
        raise HTTPException(status_code=404, detail="Run ID not found")
    
    return {"run_id": run_id, "status": status}

@app.get("/results/{run_id}")
async def get_results(run_id: str):
    results_path = settings.results_dir_abs / run_id / "results.json"
    
    if not results_path.exists():
        # Check if job failed
        status = job_status.get(run_id)
        if status and status.startswith("FAILED"):
             return {"error": status}
        return {"status": "PENDING", "message": "Results not ready yet"}
        
    try:
        with open(results_path, "r") as f:
            data = json.load(f)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read results: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

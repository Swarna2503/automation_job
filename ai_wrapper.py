from fastapi import FastAPI
from pydantic import BaseModel
import csv
import os

app = FastAPI()

class ApplyRequest(BaseModel):
    csv_path: str = "usa_jobs_ranked_full.csv"
    min_score: int = 70

@app.post("/get_jobs")
def get_jobs(request: ApplyRequest):
    """Return list of jobs with score >= min_score for UiPath to process."""
    jobs = []
    try:
        with open(request.csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            jobs = [row for row in reader if int(row.get("score", 0)) >= request.min_score]
    except FileNotFoundError:
        return {"error": "CSV not found"}
    return {"jobs": jobs}
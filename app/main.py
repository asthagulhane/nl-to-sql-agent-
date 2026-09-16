import os
from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel
from app.llm_service import generate_and_run


app = FastAPI()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

@app.get("/ui")
def serve_frontend():
    return FileResponse(os.path.join(BASE_DIR, "app", "index.html"))


# This defines the exact shape of data the /query endpoint expects.
# FastAPI automatically checks incoming requests against this and
# rejects anything that doesn't match, with a clear error message.
class QuestionRequest(BaseModel):
    question: str


@app.get("/")
def read_root():
    return {"message": "NL-to-SQL Agent is alive!"}


@app.post("/query")
def query(request: QuestionRequest):
    """
    Takes a plain-English question, runs it through the self-correcting
    agent, and returns the final SQL, the results, and the full attempt
    history (so retries are visible to whoever calls this endpoint).
    """
    result = generate_and_run(request.question)
    return result
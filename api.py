from fastapi import FastAPI
from pydantic import BaseModel
from main import run_agent
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="posts"), name="static")

THREAD_ID = "anonymus-main-chat-1"

class UserInput(BaseModel):
    topic: str


@app.get("/")
async def read_root():
    try:
        return {"Message": "Hi From Automatic Social Media Posting Agent."}
    
    except Exception as e:
        return {"Error": e}

@app.get("/health")
async def health():
    try:
        return {"Health Check": "OK"}
    
    except Exception as e:
        return {"Error": e}

@app.post("/task/{query}")
async def query(query):
    try:

        result = await run_agent(query)

        if result:
            return {"Content": result}
        else:
            return {"Content": "Error"}
        
    except Exception as e:
        print(e)
        return {"Error": e}
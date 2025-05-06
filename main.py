from fastapi import FastAPI, HTTPException, Request

from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from extraction import NotionLangSmithSync
import os
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

app = FastAPI()

# Serve static HTML files from /public directory
app.mount("/", StaticFiles(directory="public", html=True), name="static")

class PageRequest(BaseModel):
    page_id: str

@app.post("/extract_prompt_to_langsmith")
async def extract_prompt_to_langsmith(request: PageRequest):
    try:
        syncer = NotionLangSmithSync()
        result_message = syncer.sync_prompt(request.page_id)
        return {"status": "success", "message": result_message}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    
def main():
    
    uvicorn.run(app, host="0.0.0.0", port=11110)

if __name__ == "__main__":
    main()


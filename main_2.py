""" API for local testing """

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from extraction import NotionLangSmithSync
from dotenv import load_dotenv
import os
import uvicorn

# Load environment variables from .env
load_dotenv()

app = FastAPI()

# # Mount static HTML directory to /static
# app.mount("/static", StaticFiles(directory="public", html=True), name="static")

# @app.get("/")
# async def serve_home():
#     return FileResponse("public/index.html")

class PageRequest(BaseModel):
    page_id: str 
    erp_value_option: int
    function_erp_option: int


@app.post("/extract_prompt_to_langsmith")
async def extract_prompt_to_langsmith(request: PageRequest):
    try:
        syncer = NotionLangSmithSync()
        result = syncer.sync_prompt(request.page_id, request.erp_value_option, request.function_erp_option)
        return result  # Already returns dict with keys like "status" and "message"
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    
def main():
    
    uvicorn.run(app, host="0.0.0.0", port=1111)

if __name__ == "__main__":
    main()

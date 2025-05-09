from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from extraction import NotionLangSmithSync
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI()

# Mount static HTML
app.mount("/static", StaticFiles(directory="public", html=True), name="static")

@app.get("/")
async def serve_home():
    return FileResponse("public/index.html")

class PageRequest(BaseModel):
    page_id: str
    erp_value_option: int
    function_erp_option: int

@app.post("/extract_prompt_to_langsmith")
async def extract_prompt_to_langsmith(request: PageRequest):
    print(">>>>>>>", request)
    try:
        syncer = NotionLangSmithSync()
        result_message = syncer.sync_prompt(
            request.page_id,
            request.erp_value_option,
            request.function_erp_option
        )
        return {"status": "success", "message": result_message}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

""" API for deployment """

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from extraction import NotionLangSmithSync
from dotenv import load_dotenv
import os
import uvicorn
from typing import Optional

load_dotenv()

app = FastAPI()

# Mount static HTML directory
app.mount("/static", StaticFiles(directory="public", html=True), name="static")


def get_langsmith_key(department: Optional[str]) -> Optional[str]:
    if department:
        env_key_name = f"{department}_LANGSMITH_KEY".upper()
        return os.getenv(env_key_name)
    return None


class ERPRequest(BaseModel):
    page_id: str
    extraction_option: int
    prompt_name: str
    prompt_id: str
    erp_value_name: str
    function_value_name: str


class LangSmithRequest(BaseModel):
    page_id: str
    extraction_option: int
    prompt_name: str
    prompt_id: str
    erp_value_option: int
    function_erp_option: int


class WordRequest(BaseModel):
    page_id: str
    extraction_option: int
    erp_value_option: int
    function_value_option: int
    updated_erp_option: int




@app.get("/")
async def serve_home(request: Request):
    department = request.query_params.get("department")
    api_key = get_langsmith_key(department)
    print("Serving home with API key:", api_key)
    return FileResponse("public/index.html")


@app.post("/extract_prompt_to_langsmith")
async def extract_prompt_to_langsmith(data: LangSmithRequest, request: Request):
    department = request.query_params.get("department")
    langsmith_api_key = get_langsmith_key(department)

    try:
        syncer = NotionLangSmithSync(
            erp_value_option=data.erp_value_option,
            function_erp_option=data.function_erp_option,
            langsmith_api_key=langsmith_api_key
        )

        result_message = syncer.sync_prompt(data.page_id, data.erp_value_option, data.function_erp_option)
        return {"status": "success", "message": result_message}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/extract_prompt_to_word")
async def extract_prompt_to_word(data: WordRequest, request: Request):
    department = request.query_params.get("department")
    langsmith_api_key = get_langsmith_key(department)

    try:
        syncer = NotionLangSmithSync(
            erp_value_option=data.erp_value_option,
            function_erp_option=data.function_erp_option,
            updated_erp_option=data.updated_erp_option,
            langsmith_api_key=langsmith_api_key
        )

        result_message = syncer.add_colored_prompt_to_doc(data.page_id)
        return {"status": "success", "message": result_message}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



def main():
    uvicorn.run(app, host="0.0.0.0", port=11110)

if __name__ == "__main__":
    main()

""" API for deployment """

from fastapi import FastAPI, HTTPException, Request, Query
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
# app.mount("/static", StaticFiles(directory="public", html=True), name="static")

# ---------------- Helper Functions ----------------

# def get_langsmith_key(department: Optional[str]) -> Optional[str]:
#     if department:
#         env_key_name = f"{department}_LANGSMITH_KEY".upper()
#         return os.getenv(env_key_name)
#     return None

# def get_database_id(department: Optional[str]) -> Optional[str]:
#     if department:
#         env_key_name = f"{department}_DATABASE_ID".upper()
#         return os.getenv(env_key_name)
#     return None

# ---------------- Models ----------------

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
    # prompt_name: str
    # prompt_id: str
    erp_value_option: int
    function_value_option: int
    overwrite_existing: bool


class WordRequest(BaseModel):
    page_id: str
    extraction_option: int
    erp_value_option: int
    function_value_option: int
    updated_erp_option: int

# ---------------- Endpoints ----------------

# @app.get("/")
# async def serve_home(request: Request):
#     department = request.query_params.get("department")
#     # api_key = get_langsmith_key(department)
#     # db_id = get_database_id(department)
#     # print("Serving home with API key:", api_key)
#     # print("Database ID:", db_id)
#     return FileResponse("public/index.html")


@app.post("/extract_prompt_to_langsmith")
async def extract_prompt_to_langsmith(data: LangSmithRequest, request: Request):
    # department = request.query_params.get("department")
    # langsmith_api_key = get_langsmith_key(department)
    # notion_database_id = get_database_id(department)

    try:
        syncer = NotionLangSmithSync(
            erp_value_option=data.erp_value_option,
            function_value_option=data.function_value_option,
            # langsmith_api_key=langsmith_api_key,
            # notion_database_id=notion_database_id
        )

        result_message = syncer.sync_prompt(data.page_id, data.overwrite_existing)
        return {"status": "success", "message": result_message}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/extract_prompt_to_word")
async def extract_prompt_to_word(data: WordRequest, request: Request):
    # department = request.query_params.get("department")
    # notion_database_id = get_database_id(department)

    try:
        syncer = NotionLangSmithSync(
            erp_value_option=data.erp_value_option,
            function_value_option=data.function_value_option,
            updated_erp_option=data.updated_erp_option,
            # notion_database_id=notion_database_id
        )

        result_message = syncer.add_colored_prompt_to_doc(data.page_id)
        return {"status": "success", "message": result_message}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# @app.get("/get_prompts_name_id")
# async def get_prompts_name_id(department: str = Query(...)):
#     try:
#         api_key = get_langsmith_key(department)
#         if not api_key:
#             raise HTTPException(status_code=400, detail="Invalid department")

#         syncer = NotionLangSmithSync(langsmith_api_key=api_key)
#         prompt_map = syncer.get_all_prompt_names_and_ids()
#         prompt_list = [f"{name} - {id}" for name, id in prompt_map.items()]
#         return {"prompts": prompt_list}

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))


def main():
    uvicorn.run(app, host="0.0.0.0", port=1111)

if __name__ == "__main__":
    main()

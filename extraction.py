from notion_client import Client as NotionClient
from langsmith import Client as LangSmithClient
from langchain.prompts import PromptTemplate
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv
import os
import re
import unicodedata


class NotionLangSmithSync:
    def __init__(self):
        load_dotenv()
        self.notion_token = os.getenv("NOTION_TOKEN")
        self.langsmith_api_key = os.getenv("LANGCHAIN_API_KEY")
        self.notion = NotionClient(auth=self.notion_token)
        self.langsmith = LangSmithClient(api_key=self.langsmith_api_key)
        self.NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

    def get_all_blocks(self, block_id, level=0):
        blocks = []
        children = self.notion.blocks.children.list(block_id)
        for block in children["results"]:
            block["level"] = level
            blocks.append(block)
            if block.get("has_children", False):
                blocks.extend(self.get_all_blocks(block["id"], level + 1))
        return blocks

    def get_page_title(self, page_id: str) -> str:
        try:
            page = self.notion.pages.retrieve(page_id=page_id)
            for prop in page["properties"].values():
                if prop["type"] == "title":
                    raw_title = "".join(part["text"]["content"] for part in prop["title"])
                    sanitized = unicodedata.normalize("NFKD", raw_title).encode("ascii", "ignore").decode("ascii")
                    sanitized = sanitized.lower()
                    sanitized = re.sub(r'[^a-z0-9_-]', '_', sanitized)
                    sanitized = re.sub(r'^[^a-z]+', '', sanitized)
                    return sanitized or "default_prompt"
            return "untitled_prompt"
        except Exception as e:
            print(f"Error retrieving or sanitizing title for page {page_id}: {e}")
            return "error_prompt"

    def get_notion_variable_value(self, database_id, variable_name):
        response = self.notion.databases.query(database_id=database_id)
        value = ""
        for row in response["results"]:
            props = row["properties"]
            name_prop = props.get("Name", {}).get("title", [])
            name = name_prop[0].get("plain_text", "").strip() if name_prop else ""
            default_value_prop = props.get("Default Value", {}).get("rich_text", [])
            default_value = default_value_prop[0].get("plain_text", "").strip() if default_value_prop else ""
            if name == variable_name:
                value = default_value
        return value

    def get_erp_value(self, page_id, erp_value_option):
        try:
            page = self.notion.pages.retrieve(page_id=page_id)
            val = "Untitled Page"
            title_prop = page["properties"].get("Name")
            if title_prop and title_prop.get("type") == "title":
                title_parts = title_prop["title"]
                val = "".join(part["text"]["content"] for part in title_parts)
            if erp_value_option == 0:
                return self.get_notion_variable_value(self.NOTION_DATABASE_ID, val)
            elif erp_value_option == 1:
                return f"@{val}@"
            else:
                return f"{{{val}}}"
        except Exception as e:
            print(f"Error retrieving page title for {page_id}: {e}")
            return "{{Error}}"

    def get_function_value(self, page_id, block_id, erp_value_option, function_value_option):
        try:
            page = self.notion.pages.retrieve(page_id=page_id)
            blocks = self.get_all_blocks(block_id)
            val = "@Function Name@"

            for block in blocks:
                if block['type'] == 'paragraph' and 'rich_text' in block['paragraph']:
                    block_content = self.extract_text(block['paragraph'], erp_value_option)

                    if function_value_option == 0:
                        if block_content.startswith("Value if no condition is met:"):
                            val = block_content.split("Value if no condition is met:")[1].strip()
                            return val

                    elif function_value_option == 1:
                        if block_content.startswith("Name*:"):
                            val = block_content.split("Name*:")[1].strip()
                            return f"@{val}@"

            # ✅ Final logic for option 2: collect all brown background child blocks
            if function_value_option == 2:
                for block in blocks:
                    if block['type'] == 'callout' and block.get('has_children'):
                        children = self.notion.blocks.children.list(block['id']).get("results", [])
                        brown_texts = []
                        for child in children:
                            if (
                                child['type'] == 'paragraph'
                                and 'paragraph' in child
                                and child['paragraph'].get('color') == 'brown_background'
                            ):
                                text = self.extract_text(child['paragraph'], erp_value_option).strip()
                                if text:
                                    brown_texts.append(text)
                        if brown_texts:
                            return " ".join(brown_texts)
                        return "{No brown background paragraphs found in callout}"

            return val
        except Exception as e:
            print(f"Error retrieving function value for {page_id}: {e}")
            return "@Error@"

    def extract_text(self, block_content, erp_value_option):
        try:
            parts = []
            for rt in block_content["rich_text"]:
                if rt.get("type") == "mention":
                    mention = rt.get("mention", {})
                    if mention.get("type") == "page":
                        page_id = mention["page"].get("id")
                        if page_id:
                            formatted_erp_value = self.get_erp_value(page_id, erp_value_option)
                            parts.append(formatted_erp_value)
                        else:
                            parts.append("{Unknown Page}")
                    else:
                        parts.append("{Mention}")
                elif rt.get("type") == "text":
                    parts.append(rt["text"].get("content", ""))
            return "".join(parts)
        except (KeyError, IndexError, TypeError):
            return ""

    def get_notion_prompt(self, page_id, erp_value_option, function_value_option):
        all_blocks = self.get_all_blocks(page_id)
        prompt = []
        list_counters = {}
        ignored_blocks = []

        for block in all_blocks:
            block_type = block["type"]
            level = block.get("level", 0)
            indent = "  " * level

            if block["parent"].get("block_id") in ignored_blocks:
                ignored_blocks.append(block["id"])
                continue

            if block_type == "toggle":
                text = self.extract_text(block["toggle"], erp_value_option)
                text_lower = text.lower()

                if "function_value" in text_lower:
                    ignored_blocks.append(block["id"])
                    formatted_function_value = self.get_function_value(page_id, block["id"], erp_value_option, function_value_option)
                    prompt.append(f"{indent}{formatted_function_value}")
                elif "update_erp_value" in text_lower:
                    ignored_blocks.append(block["id"])
                continue

            block_data = block.get(block_type)
            if not block_data:
                continue

            text = self.extract_text(block_data, erp_value_option)
            if not text:
                continue

            if block_type == "bulleted_list_item":
                formatted = f"{indent}- {text}"
            elif block_type == "numbered_list_item":
                list_counters[level] = list_counters.get(level, 0) + 1
                for deeper_level in list(filter(lambda l: l > level, list_counters)):
                    list_counters[deeper_level] = 0
                formatted = f"{indent}{list_counters[level]}. {text}"
            else:
                formatted = f"{indent}{text}"

            prompt.append(formatted)

        return prompt

    def sync_prompt(self, page_id: str, erp_value_option: int, function_value_option: int):
        paragraphs = self.get_notion_prompt(page_id, erp_value_option, function_value_option)
        system_message = "\n".join(paragraphs)
        chat_prompt_template = ChatPromptTemplate([
            ("system", system_message),
            ("user", "{Conversation}"),
        ])

        prompt_identifier = self.get_page_title(page_id).strip().replace(" ", "_").lower()

        print(f"\nUsing prompt identifier: {prompt_identifier}")
        print(system_message)
        print(f"\nTotal lines in prompt: {len(paragraphs)}")

        try:
            self.langsmith.push_prompt(
                prompt_identifier=prompt_identifier,
                object=chat_prompt_template,
                description="Updated prompt with content"
            )
            print(f" Successfully updated existing prompt: {prompt_identifier}")
            return {"status": "updated", "message": "Prompt updated successfully."}

        except Exception as e:
            error_msg = str(e)

            if "not found" in error_msg.lower():
                print(f"Prompt {prompt_identifier} not found. Creating new prompt...")
                self.langsmith.create_prompt(
                    prompt_identifier=prompt_identifier,
                    description="Prompt created from Notion page",
                    tags=["notion", "auto-sync"],
                    is_public=False
                )
                self.langsmith.push_prompt(
                    prompt_identifier=prompt_identifier,
                    object=chat_prompt_template,
                    description="Populated newly created prompt"
                )
                print(f" Successfully created and populated new prompt: {prompt_identifier}")
                return {"status": "created", "message": "Prompt created and pushed successfully."}

            elif "Nothing to commit" in error_msg:
                print(f" No changes in prompt: {prompt_identifier}. Skipping push.")
                return {"status": "skipped", "message": "Prompt not updated — no changes detected."}

            else:
                raise e

from notion_client import Client as NotionClient
from langsmith import Client as LangSmithClient
from langchain.prompts import PromptTemplate
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
            # Extract the default Notion page title
            for prop in page["properties"].values():
                if prop["type"] == "title":
                    raw_title = "".join(part["text"]["content"] for part in prop["title"])
                    
                    # Sanitize the title for use as a prompt_identifier
                    sanitized = unicodedata.normalize("NFKD", raw_title).encode("ascii", "ignore").decode("ascii")
                    sanitized = sanitized.lower()
                    sanitized = re.sub(r'[^a-z0-9_-]', '_', sanitized)
                    sanitized = re.sub(r'^[^a-z]+', '', sanitized)
                    return sanitized or "default_prompt"

            return "untitled_prompt"

        except Exception as e:
            print(f"Error retrieving or sanitizing title for page {page_id}: {e}")
            return "error_prompt"


    def extract_text(self, block_content):
        try:
            parts = []
            for rt in block_content["rich_text"]:
                if rt.get("type") == "mention":
                    mention = rt.get("mention", {})
                    if mention.get("type") == "page":
                        page_id = mention["page"].get("id")
                        if page_id:
                            page_title = self.get_page_title(page_id)
                            parts.append(f"{{{page_title}}}")
                        else:
                            parts.append("{Unknown Page}")
                    else:
                        parts.append("{Mention}")
                elif rt.get("type") == "text":
                    parts.append(rt["text"].get("content", ""))
            return "".join(parts)
        except (KeyError, IndexError, TypeError):
            return ""

    def get_notion_prompt(self, page_id):
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
                text = self.extract_text(block["toggle"])
                text_lower = text.lower()

                if "function_value" in text_lower:
                    ignored_blocks.append(block["id"])
                    if ":" in text:
                        name = text.split(":", 1)[1].strip()
                        prompt.append(f"{indent}@{name}@")
                    else:
                        prompt.append(f"{indent}{text}")
                elif "update_erp_value" in text_lower:
                    ignored_blocks.append(block["id"])
                continue

            block_data = block.get(block_type)
            if not block_data:
                continue

            text = self.extract_text(block_data)
            if not text:
                continue

            text = re.sub(r"\{(\w+)\}", r"@\1@", text)

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

    def sync_prompt(self, page_id: str):
        # Extract Notion prompt text
        paragraphs = self.get_notion_prompt(page_id)
        prompt_template = PromptTemplate(
            input_variables=["input"],
            template="\n".join(paragraphs)
        )

        # Use Notion title as prompt identifier
        prompt_identifier = self.get_page_title(page_id).strip().replace(" ", "_").lower()

        print(f"\nUsing prompt identifier: {prompt_identifier}")
        print("\n".join(paragraphs))
        print(f"\nTotal lines in prompt: {len(paragraphs)}")

        try:
            self.langsmith.push_prompt(
                prompt_identifier=prompt_identifier,
                object=prompt_template,
                description="Updated prompt with content"
            )
            print(f"✅ Successfully updated existing prompt: {prompt_identifier}")
        except Exception as e:
            if "not found" in str(e).lower():
                print(f"Prompt {prompt_identifier} not found. Creating new prompt...")
                self.langsmith.create_prompt(
                    prompt_identifier=prompt_identifier,
                    description="Prompt created from Notion page",
                    tags=["notion", "auto-sync"],
                    is_public=False
                )
                self.langsmith.push_prompt(
                    prompt_identifier=prompt_identifier,
                    object=prompt_template,
                    description="Populated newly created prompt"
                )
                print(f"✅ Successfully created and populated new prompt: {prompt_identifier}")
            else:
                raise e

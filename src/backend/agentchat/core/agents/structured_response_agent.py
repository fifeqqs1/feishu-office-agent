import json
import re
from pydantic import BaseModel
from langchain_core.messages import SystemMessage, HumanMessage

from agentchat.core.callbacks import usage_metadata_callback
from agentchat.core.models.manager import ModelManager


class StructuredResponseAgent:
    def __init__(self, response_format):
        self.response_format = response_format
        self.model = ModelManager.get_conversation_model()

    def get_structured_response(self, messages):
        prompt = messages if isinstance(messages, str) else json.dumps(messages, ensure_ascii=False)

        model_messages = [
            SystemMessage(content="你是一个只输出JSON对象的助手。不要输出Markdown，不要输出额外文字。"),
            HumanMessage(content=prompt),
        ]

        result = self.model.invoke(
            model_messages,
            config={"callbacks": [usage_metadata_callback]},
        )
        content = (getattr(result, "content", None) or "").strip()

        try:
            return self.response_format.model_validate_json(content)
        except Exception:
            match = re.search(r"\{[\s\S]*\}", content)
            if match:
                try:
                    return self.response_format.model_validate_json(match.group(0))
                except Exception:
                    pass
            raise ValueError(f"Invalid structured JSON output: {content}")

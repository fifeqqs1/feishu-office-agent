from pathlib import Path
import yaml
from typing import Literal, Optional
from loguru import logger
from types import SimpleNamespace
from pydantic.v1 import BaseSettings, Field

from agentchat.schema.common import MultiModels, ModelConfig, Tools, Rag, StorageConfig


class Settings(BaseSettings):
    redis: dict = {}
    mysql: dict = {}
    server: dict = {}
    langfuse: dict = {}
    whitelist_paths: list = []
    wechat_config: dict = {}
    default_config: dict = {}

    rag: Optional[Rag] = None
    tools: Optional[Tools] = None
    storage: Optional[StorageConfig] = None
    multi_models: Optional[MultiModels] = None


app_settings = Settings()


def _resolve_settings_file(file_path: str | None = None) -> str:
    base_path = Path(file_path or "agentchat/config.yaml")

    if base_path.name == "config.yaml":
        local_override = base_path.with_name("config_ceshi.yaml")
        if local_override.exists():
            return str(local_override)
        if base_path.exists():
            return str(base_path)
        example_file = base_path.with_name("config.example.yaml")
        if example_file.exists():
            logger.warning("Local config.yaml not found, using config.example.yaml as a template")
            return str(example_file)

    return str(base_path)


async def initialize_app_settings(file_path: str = None):
    global app_settings

    file_path = _resolve_settings_file(file_path)
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            if data is None:
                logger.error("YAML 文件解析为空")
                return

            # 特殊处理multi_models配置
            if "multi_models" in data:
                data["multi_models"] = MultiModels(**data["multi_models"])

            if "tools" in data:
                data["tools"] = Tools(**data["tools"])

            if "rag" in data:
                data["rag"] = Rag(**data["rag"])

            if "storage" in data:
                data["storage"] = StorageConfig(**data["storage"])

            for key, value in data.items():
                setattr(app_settings, key, value)
    except Exception as e:
        logger.error(f"Yaml file loading error: {e}")

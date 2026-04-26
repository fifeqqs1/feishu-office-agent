import json
from loguru import logger
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, SystemMessage
from starlette.responses import StreamingResponse

from agentchat.core.callbacks import usage_metadata_callback
from agentchat.core.models.manager import ModelManager
from agentchat.api.services.llm import LLMService
from agentchat.api.services.mcp_server import MCPService
from agentchat.api.services.tool import ToolService
from agentchat.api.services.workspace_session import WorkSpaceSessionService
from agentchat.prompts.completion import SYSTEM_PROMPT
from agentchat.schema.schemas import resp_200
from agentchat.schema.usage_stats import UsageStatsAgentType
from agentchat.schema.workspace import WorkSpaceSimpleTask
from agentchat.api.services.user import UserPayload, get_login_user
from agentchat.database.dao.user import UserDao
from agentchat.services.workspace.simple_agent import WorkSpaceSimpleAgent, MCPConfig
from agentchat.services.memory.client import memory_client
from agentchat.utils.contexts import set_user_id_context, set_agent_name_context
from agentchat.utils.date_utils import get_beijing_time

router = APIRouter(prefix="/workspace", tags=["WorkSpace"])


class WorkSpaceCapabilitySelection(BaseModel):
    plugin_ids: list[str] = []
    mcp_server_ids: list[str] = []


def _extract_first_json_object(content: str) -> dict:
    content = (content or "").strip()
    if not content:
        return {}

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(content[start:end + 1])
            except json.JSONDecodeError:
                return {}
    return {}


def _heuristic_select_plugin_ids(query: str, visible_tools: list[dict]) -> list[str]:
    lowered_query = query.lower()
    tool_by_name = {
        tool.get("name"): tool.get("tool_id")
        for tool in visible_tools
        if tool.get("name") and tool.get("tool_id")
    }
    selected_ids: list[str] = []

    def select_tool(*tool_names: str):
        for tool_name in tool_names:
            tool_id = tool_by_name.get(tool_name)
            if tool_id and tool_id not in selected_ids:
                selected_ids.append(tool_id)
                return True
        return False

    if any(keyword in lowered_query for keyword in ("天气", "气温", "温度", "下雨", "晴", "阴", "雪")):
        select_tool("get_weather")

    if any(keyword in lowered_query for keyword in ("论文", "paper", "arxiv", "文献", "研究进展")):
        select_tool("get_arxiv")

    if any(keyword in lowered_query for keyword in ("快递", "物流", "运单", "包裹")):
        select_tool("get_delivery", "get_delivery_info")

    if any(keyword in lowered_query for keyword in ("邮件", "email", "发信", "发邮件")):
        select_tool("send_email")

    if any(keyword in lowered_query for keyword in ("生成图片", "画一张", "画个", "作图", "图片生成")):
        select_tool("text_to_image")

    if any(keyword in lowered_query for keyword in ("pdf转docx", "pdf 转 docx", "转成word", "转成 docx")):
        select_tool("convert_to_docx")

    if any(keyword in lowered_query for keyword in ("docx转pdf", "docx 转 pdf", "转成pdf", "转成 pdf")):
        select_tool("convert_to_pdf")

    if any(keyword in lowered_query for keyword in ("最新", "新闻", "比赛", "赛程", "官网", "查一下", "搜索", "联网", "今天有")):
        select_tool("tavily_search", "bocha_search")

    return selected_ids


async def _select_capabilities_with_model(
    query: str,
    visible_tools: list[dict],
    visible_servers: list[dict],
    model_config: dict,
) -> WorkSpaceCapabilitySelection:
    if not visible_tools and not visible_servers:
        return WorkSpaceCapabilitySelection()

    selector_prompt = {
        "query": query,
        "plugins": [
            {
                "tool_id": tool.get("tool_id"),
                "name": tool.get("name"),
                "display_name": tool.get("display_name"),
                "description": tool.get("description"),
            }
            for tool in visible_tools
        ],
        "mcp_servers": [
            {
                "mcp_server_id": server.get("mcp_server_id"),
                "server_name": server.get("server_name"),
                "description": server.get("description"),
                "tools": server.get("tools", []),
            }
            for server in visible_servers
        ],
    }

    selector_model = ModelManager.get_user_model(**model_config).bind(response_format={"type": "json_object"})
    response = await selector_model.ainvoke(
        [
            SystemMessage(content=(
                "你是工作台能力路由器。"
                "请根据用户问题，从给定插件和 MCP 服务里挑出完成当前问题真正需要的最小集合。"
                "如果问题只是普通闲聊或无需外部能力，返回空数组。"
                "返回 JSON 对象，格式必须是 "
                "{\"plugin_ids\": [\"...\"], \"mcp_server_ids\": [\"...\"]}。"
                "不要返回列表之外的 ID，不要附加解释。"
            )),
            HumanMessage(content=json.dumps(selector_prompt, ensure_ascii=False)),
        ],
        config={"callbacks": [usage_metadata_callback]},
    )
    selection_payload = _extract_first_json_object(getattr(response, "content", "") or "")
    if not selection_payload:
        return WorkSpaceCapabilitySelection()
    return WorkSpaceCapabilitySelection.model_validate(selection_payload)


async def _resolve_workspace_capabilities(simple_task: WorkSpaceSimpleTask, user_id: str, model_config: dict):
    plugin_ids = list(simple_task.plugins or [])
    mcp_server_ids = list(simple_task.mcp_servers or [])

    visible_tools = await ToolService.get_visible_tool_by_user(user_id) if not plugin_ids else []
    visible_servers = await MCPService.get_all_servers(user_id) if not mcp_server_ids else []

    selected_by_rule = _heuristic_select_plugin_ids(simple_task.query, visible_tools) if not plugin_ids else []
    selected_by_model = WorkSpaceCapabilitySelection()

    if (not plugin_ids or not mcp_server_ids) and (
        (visible_tools and not selected_by_rule) or visible_servers
    ):
        try:
            selected_by_model = await _select_capabilities_with_model(
                query=simple_task.query,
                visible_tools=visible_tools,
                visible_servers=visible_servers,
                model_config=model_config,
            )
        except Exception as err:
            logger.warning(f"Workspace auto-selection model failed: {err}")

    if not plugin_ids:
        visible_tool_ids = {tool["tool_id"] for tool in visible_tools if tool.get("tool_id")}
        plugin_ids = [
            tool_id
            for tool_id in (selected_by_rule or selected_by_model.plugin_ids)
            if tool_id in visible_tool_ids
        ]

    if not mcp_server_ids:
        visible_server_ids = {server["mcp_server_id"] for server in visible_servers if server.get("mcp_server_id")}
        mcp_server_ids = [
            server_id
            for server_id in selected_by_model.mcp_server_ids
            if server_id in visible_server_ids
        ]

    logger.info(
        f"Workspace simple chat resolved capabilities for user {user_id}: "
        f"plugins={len(plugin_ids)}, mcps={len(mcp_server_ids)}"
    )
    return plugin_ids, mcp_server_ids


@router.get("/plugins", summary="获取工作台的可用插件")
async def get_workspace_plugins(login_user: UserPayload = Depends(get_login_user)):
    results = await ToolService.get_visible_tool_by_user(login_user.user_id)
    return resp_200(data=results)

@router.get("/session", summary="获取工作台所有会话列表")
async def get_workspace_sessions(login_user: UserPayload = Depends(get_login_user)):
    results = await WorkSpaceSessionService.get_workspace_sessions(login_user.user_id)
    return resp_200(data=results)


@router.post("/session", summary="创建工作台会话")
async def create_workspace_session(*,
                                   title: str = "",
                                   contexts: dict = {},
                                   login_user: UserPayload = Depends(get_login_user)):
    pass

@router.post("/session/{session_id}", summary="进入工作台会话")
async def workspace_session_info(session_id: str,
                                 login_user: UserPayload = Depends(get_login_user)):
    try:
        result = await WorkSpaceSessionService.get_workspace_session_from_id(session_id, login_user.user_id)
        return resp_200(data=result)
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))

@router.delete("/session", summary="删除工作台的会话")
async def create_workspace_session(session_id: str,
                                   login_user: UserPayload = Depends(get_login_user)):
    try:
        await WorkSpaceSessionService.delete_workspace_session([session_id], login_user.user_id)
        return resp_200()
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))


@router.post("/simple/chat", summary="工作台日常对话")
async def workspace_simple_chat(simple_task: WorkSpaceSimpleTask,
                                login_user: UserPayload = Depends(get_login_user)):
    # 设置全局变量统计调用
    set_user_id_context(login_user.user_id)
    set_agent_name_context(UsageStatsAgentType.simple_agent)

    model_config = await LLMService.get_llm_by_id(simple_task.model_id)
    plugin_ids, mcp_server_ids = await _resolve_workspace_capabilities(
        simple_task,
        login_user.user_id,
        {
            "model": model_config["model"],
            "base_url": model_config["base_url"],
            "api_key": model_config["api_key"],
            "user_id": login_user.user_id,
        },
    )
    servers_config = []
    for mcp_id in mcp_server_ids:
        mcp_server = await MCPService.get_mcp_server_from_id(mcp_id)
        servers_config.append(
            MCPConfig(**mcp_server)
        )

    simple_agent = WorkSpaceSimpleAgent(
        model_config={
            "model": model_config["model"],
            "base_url": model_config["base_url"],
            "api_key": model_config["api_key"],
            "user_id": login_user.user_id,
        },
        mcp_configs=servers_config,
        plugins=plugin_ids,
        user_id=login_user.user_id,
        session_id=simple_task.session_id
    )

    workspace_session = await WorkSpaceSessionService.get_workspace_session_from_id(simple_task.session_id, login_user.user_id)
    if workspace_session:
        contexts = workspace_session.get("contexts", [])
        history_messages = [
            f"query: {message.get('query')}, answer: {message.get('answer')}\n"
            for message in contexts
        ]
    else:
        history_messages = "无历史对话"

    user_profile_lines = []
    db_user = UserDao.get_user(login_user.user_id)
    if db_user:
        if db_user.user_name:
            user_profile_lines.append(f"- 用户名：{db_user.user_name}")
        if db_user.user_description:
            user_profile_lines.append(f"- 用户描述：{db_user.user_description}")

    if not user_profile_lines:
        user_profile_lines.append("- 暂无可用的用户资料")

    memory_lines = []
    try:
        memory_result = await memory_client.search(
            query=simple_task.query,
            user_id=login_user.user_id,
            limit=5,
        )
        for item in memory_result.get("results", []):
            memory_text = item.get("memory", "").strip()
            if memory_text:
                memory_lines.append(f"- {memory_text}")
    except Exception as err:
        logger.warning(f"Failed to retrieve long-term memory for workspace chat: {err}")

    if not memory_lines:
        memory_lines.append("- 暂未检索到与当前问题相关的长期记忆")

    current_beijing_time = get_beijing_time()
    system_prompt = (
        SYSTEM_PROMPT.format(history=str(history_messages))
        + "\n\n👤 当前用户资料：\n"
        + "\n".join(user_profile_lines)
        + "\n\n🧠 用户长期记忆（跨对话召回）：\n"
        + "\n".join(memory_lines)
        + "\n\n🕒 当前北京时间（UTC+8）："
        + current_beijing_time
        + "\n- 该时间适用于中国大陆城市，例如武汉、北京、上海。"
        + "\n- 当用户询问当前时间、现在几点、今天几号等实时问题时，请优先基于这个时间回答。"
        + "\n- 如果用户询问其他国家或地区的当前时间，而你没有对应工具，请明确说明你当前仅掌握北京时间。"
        + "\n- 当用户询问“我是谁”“你还记得我吗”“我之前说过什么”时，请优先结合用户资料与长期记忆回答。"
    )

    async def general_generate():
        async for chunk in simple_agent.astream([
            SystemMessage(content=system_prompt),
            HumanMessage(content=simple_task.query)
        ]):
            # chunk 已经是 dict: {"event": "task_result", "data": {"message": "..."}}
            # 需要 JSON 序列化后作为 SSE 的 data 字段
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        general_generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )

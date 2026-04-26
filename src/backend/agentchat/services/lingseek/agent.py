import json
from typing import List, Union, Optional

from loguru import logger
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage, BaseMessage, AIMessageChunk
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import BaseModel

from agentchat.api.services.mcp_server import MCPService
from agentchat.api.services.mcp_user_config import MCPUserConfigService
from agentchat.api.services.usage_stats import UsageStatsService
from agentchat.api.services.workspace_session import WorkSpaceSessionService
from agentchat.core.callbacks import usage_metadata_callback
from agentchat.database.models.workspace_session import WorkSpaceSessionCreate, WorkSpaceSessionContext
from agentchat.prompts.template import GuidePromptTemplate
from agentchat.schema.workspace import WorkSpaceAgents
from agentchat.schema.usage_stats import UsageStatsAgentType
from agentchat.core.agents.mcp_agent import MCPConfig
from agentchat.tools import LingSeekPlugins, tavily_search as web_search
from agentchat.api.services.tool import ToolService
from agentchat.core.models.manager import ModelManager
from agentchat.utils.convert import mcp_tool_to_args_schema, convert_mcp_config
from agentchat.utils.date_utils import get_beijing_time
from agentchat.services.mcp.manager import MCPManager
from agentchat.prompts.lingseek import GenerateGuidePrompt, FeedBackGuidePrompt, GenerateTitlePrompt, \
    GenerateTaskPrompt, FixJsonPrompt, ToolCallPrompt, SystemMessagePrompt
from agentchat.schema.lingseek import LingSeekGuidePrompt, LingSeekGuidePromptFeedBack, LingSeekTask, \
    LingSeekTaskStep


class LingSeekCapabilitySelection(BaseModel):
    plugin_ids: List[str] = []
    mcp_server_ids: List[str] = []


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


class LingSeekAgent:
    conversation_model = ModelManager.get_conversation_model()
    tool_call_model = ModelManager.get_lingseek_intent_model()

    def __init__(self, user_id: str):
        self.mcp_manager: Optional[MCPManager] = None
        self.mcp_tools = []
        self.tool_mcp_server_dict = {}

        self.user_id = user_id

    async def _select_capabilities_with_model(
        self,
        query: str,
        visible_tools: list[dict],
        visible_servers: list[dict],
    ) -> LingSeekCapabilitySelection:
        if not visible_tools and not visible_servers:
            return LingSeekCapabilitySelection()

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

        selector_model = self.tool_call_model.bind(response_format={"type": "json_object"})
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
            return LingSeekCapabilitySelection()
        return LingSeekCapabilitySelection.model_validate(selection_payload)

    async def _resolve_lingseek_capabilities(
        self,
        query: str,
        plugins: list[str],
        mcp_servers: list[str],
    ) -> tuple[list[str], list[str]]:
        plugin_ids = list(plugins or [])
        mcp_server_ids = list(mcp_servers or [])

        visible_tools = await ToolService.get_visible_tool_by_user(self.user_id) if not plugin_ids else []
        visible_servers = await MCPService.get_all_servers(self.user_id) if not mcp_server_ids else []

        selected_by_rule = _heuristic_select_plugin_ids(query, visible_tools) if not plugin_ids else []
        selected_by_model = LingSeekCapabilitySelection()

        if (not plugin_ids or not mcp_server_ids) and ((visible_tools and not selected_by_rule) or visible_servers):
            try:
                selected_by_model = await self._select_capabilities_with_model(
                    query=query,
                    visible_tools=visible_tools,
                    visible_servers=visible_servers,
                )
            except Exception as err:
                logger.warning(f"LingSeek auto-selection model failed: {err}")

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
            f"LingSeek resolved capabilities for user {self.user_id}: "
            f"plugins={len(plugin_ids)}, mcps={len(mcp_server_ids)}"
        )
        return plugin_ids, mcp_server_ids

    async def _normalize_capabilities(
        self,
        lingseek_info: Union[LingSeekGuidePrompt, LingSeekGuidePromptFeedBack, LingSeekTask],
    ):
        plugin_ids, mcp_server_ids = await self._resolve_lingseek_capabilities(
            query=lingseek_info.query,
            plugins=lingseek_info.plugins,
            mcp_servers=lingseek_info.mcp_servers,
        )
        return lingseek_info.model_copy(
            update={
                "plugins": plugin_ids,
                "mcp_servers": mcp_server_ids,
            }
        )

    async def _generate_guide_prompt(self, lingseek_guide_prompt):
        """
        通过COT的方法使得模型回复的更加准确，但是展示的时候需要把思考内容隐藏
        """
        one = None
        sop_flag = False
        sop_content = ""
        answer = ""
        split_tags = ["<Thought_END>", "</Thought_END>"]
        async for one in self.conversation_model.astream(input=lingseek_guide_prompt, config={"callbacks": [usage_metadata_callback]}):
            answer += f"{one.content}"
            if sop_flag:
                yield one
                sop_content += one.content
                continue
            for split_tag in split_tags:
                if answer.find(split_tag) != -1:
                    sop_flag = True
                    sop_content = answer.split(split_tag)[-1].strip()
                    if sop_content:
                        one.content = sop_content
                        yield one
                    break
        if not sop_content:
            one.content = answer
            yield one

    async def _generate_tasks(self, lingseek_task_prompt):
        conversation_json_model = self.conversation_model.bind(response_format={"type": "json_object"})

        response = await conversation_json_model.ainvoke(input=lingseek_task_prompt, config={"callbacks": [usage_metadata_callback]})

        try:
            content = json.loads(response.content)
            return content
        except Exception as err:
            fix_message = FixJsonPrompt.format(json_content=response.content, json_error=str(err))
            fix_response = await conversation_json_model.ainvoke(input=fix_message, config={"callbacks": [usage_metadata_callback]})
            try:
                fix_content = json.loads(fix_response.content)
                return fix_content
            except Exception as fix_err:
                raise ValueError(fix_err)

    async def _generate_title(self, query):
        title_prompt = GenerateTitlePrompt.format(query=query)
        response = await self.conversation_model.ainvoke(input=title_prompt, config={"callbacks": [usage_metadata_callback]})
        return response.content

    async def _add_workspace_session(self, query, contexts: WorkSpaceSessionContext):
        title = await self._generate_title(query)
        await WorkSpaceSessionService.create_workspace_session(
            WorkSpaceSessionCreate(
                title=title,
                user_id=self.user_id,
                contexts=[contexts.model_dump()],
                agent=WorkSpaceAgents.LingSeekAgent.value))

    async def _parse_function_call_response(self, message: AIMessage):
        tool_messages = []
        if message.tool_calls:
            for tool_call in message.tool_calls:
                tool_name = tool_call.get("name")
                tool_args = tool_call.get("args")
                tool_call_id = tool_call.get("id")

                content = await self._process_tools_result(tool_name, tool_args)
                tool_messages.append(ToolMessage(content=content, name=tool_name, tool_call_id=tool_call_id))

        return tool_messages

    async def generate_tasks(self, lingseek_task: LingSeekTask, capabilities_resolved: bool = False):
        if not capabilities_resolved:
            lingseek_task = await self._normalize_capabilities(lingseek_task)

        tools = await self._obtain_lingseek_tools(lingseek_task.plugins, lingseek_task.mcp_servers, lingseek_task.web_search)
        tools_str = json.dumps(tools, ensure_ascii=False, indent=2)

        lingseek_task_prompt = GenerateTaskPrompt.format(
            tools_str=tools_str,
            query=lingseek_task.query,
            guide_prompt=lingseek_task.guide_prompt,
            current_time=get_beijing_time(),
        )

        response_task = await self._generate_tasks(lingseek_task_prompt)
        return response_task

    async def generate_guide_prompt(self, lingseek_info: Union[LingSeekGuidePrompt, LingSeekGuidePromptFeedBack],
                                    feedback: bool = False):
        lingseek_info = await self._normalize_capabilities(lingseek_info)

        tools = await self._obtain_lingseek_tools(lingseek_info.plugins, lingseek_info.mcp_servers, lingseek_info.web_search)
        tools_str = json.dumps(tools, ensure_ascii=False, indent=2)

        if feedback:
            lingseek_guide_prompt = FeedBackGuidePrompt.format(
                query=lingseek_info.query,
                tools_str=tools_str,
                feedback=lingseek_info.feedback,
                feedback_guide_prompt=lingseek_info.guide_prompt,
            )
        else:
            lingseek_guide_prompt = GenerateGuidePrompt.format(
                tools_str=tools_str,
                query=lingseek_info.query,
                guide_prompt_template=GuidePromptTemplate,
            )
        async for chunk in self._generate_guide_prompt(lingseek_guide_prompt):
            yield {
                "event": "generate_guide_prompt",
                "data": {
                    "chunk": chunk.content
                }
            }


    async def submit_lingseek_task(self, lingseek_task: LingSeekTask):
        lingseek_task = await self._normalize_capabilities(lingseek_task)
        task = await self.generate_tasks(lingseek_task, capabilities_resolved=True)

        tasks_graph = {}
        tasks_show = []
        steps = task.get("steps", [])
        for step in steps:
            task_step = LingSeekTaskStep(**step)
            tasks_graph[task_step.step_id] = task_step

        for step_id, step_info in tasks_graph.items():
            for input_step in step_info.input:
                if input_step in tasks_graph:
                    # 构建展示的任务列表图结构
                    tasks_show.append({
                        "start": tasks_graph[input_step].title,
                        "end": tasks_graph[step_id].title
                    })
                else:
                    tasks_show.append({
                        "start": "用户问题",
                        "end": tasks_graph[step_id].title
                    })
        yield {
            "event": "generate_tasks",
            "data": {"graph": tasks_show}
        }


        tools = await self._obtain_lingseek_tools(lingseek_task.plugins, lingseek_task.mcp_servers, lingseek_task.web_search)
        tool_call_model = self.tool_call_model.bind_tools(tools) if len(tools) else self.tool_call_model

        messages: List[BaseMessage] = [SystemMessage(content=SystemMessagePrompt), HumanMessage(content=lingseek_task.query)]
        context_task = []
        for step_id, step_info in tasks_graph.items():
            step_context = []
            for input_step in step_info.input:
                if input_step in tasks_graph:
                    step_context.append(
                        tasks_graph[input_step].model_dump()
                    )

            step_prompt = ToolCallPrompt.format(
                step_info=step_info,
                step_context=str(step_context)
            )
            step_messages = [SystemMessage(content=step_prompt), HumanMessage(content=lingseek_task.query)]
            response = await tool_call_model.ainvoke(input=step_messages, config={"callbacks": [usage_metadata_callback]})

            tools_messages = await self._parse_function_call_response(response)

            step_info.result = "\n".join([msg.content for msg in tools_messages])

            context_task.append(step_info.model_dump())
            if tools_messages: # 合到整体Messages
                messages.append(response)
                messages.extend(tools_messages)
            else:
                messages.append(HumanMessage(content=lingseek_task.query))
                messages.append(AIMessage(content=response.content))
            yield {
                "event": "step_result",
                "data": {"message": step_info.result or " ", "title": step_info.title}
            }

        final_response = ""
        async for chunk in self.conversation_model.astream(messages):
            final_response += chunk.content
            yield {
                "event": "task_result",
                "data": {"message": chunk.content}
            }

        await self._add_workspace_session(
            lingseek_task.query,
            WorkSpaceSessionContext(
                query=lingseek_task.query,
                guide_prompt=lingseek_task.guide_prompt,
                task=context_task,
                task_graph=tasks_show,
                answer=final_response
            ))

    async def _process_tools_result(self, tool_name, tool_args):
        def find_mcp_tool(tool_name):
            """Find MCP tool by name"""
            for tool in self.mcp_tools:
                if tool.name == tool_name:
                    return tool
            return None

        if tool := find_mcp_tool(tool_name):
            mcp_config = await MCPUserConfigService.get_mcp_user_config(self.user_id,
                                                                        self.tool_mcp_server_dict[tool_name])
            tool_args.update(mcp_config)
            text_content, no_text_content = await tool.coroutine(**tool_args)
        else:
            text_content = LingSeekPlugins[tool_name].invoke(tool_args)
        return text_content

    async def _obtain_lingseek_tools(self, plugins, mcp_servers, enable_web_search=False):
        plugins_name = await ToolService.get_tool_name_by_id(plugins)
        unsupported_plugins = [name for name in plugins_name if LingSeekPlugins.get(name) is None]
        if unsupported_plugins:
            logger.warning(f"LingSeek ignored unsupported plugins: {unsupported_plugins}")

        plugins_func = [LingSeekPlugins.get(name) for name in plugins_name if LingSeekPlugins.get(name) is not None]
        tools = [convert_to_openai_tool(func) for func in plugins_func]

        if enable_web_search and web_search not in plugins_func:
            plugins_func.append(web_search)
            tools.append(convert_to_openai_tool(web_search))

        async def get_mcp_tools():
            if self.mcp_tools:
                return self.mcp_tools

            servers_config = []
            for mcp_id in mcp_servers:
                mcp_server = await MCPService.get_mcp_server_from_id(mcp_id)
                mcp_config = MCPConfig(**mcp_server)

                self.tool_mcp_server_dict.update({tool: mcp_config.mcp_server_id for tool in mcp_config.tools})
                servers_config.append(
                    convert_mcp_config(mcp_config.model_dump())
                )
            self.mcp_manager = MCPManager(servers_config)
            mcp_tools = await self.mcp_manager.get_mcp_tools()
            self.mcp_tools = mcp_tools

            return mcp_tools

        mcp_tools = await get_mcp_tools()
        mcp_tools = [mcp_tool_to_args_schema(tool.name, tool.description, tool.args_schema) for tool in mcp_tools]
        tools.extend(mcp_tools)

        return tools

    async def _record_agent_token_usage(self, response: AIMessage | AIMessageChunk | BaseMessage, model):
        if response.usage_metadata:
            await UsageStatsService.create_usage_stats(
                model=model,
                user_id=self.user_id,
                agent=UsageStatsAgentType.lingseek_agent,
                input_tokens=response.usage_metadata.get("input_tokens"),
                output_tokens=response.usage_metadata.get("output_tokens")
            )

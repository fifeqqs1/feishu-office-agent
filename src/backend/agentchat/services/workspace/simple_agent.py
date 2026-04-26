import copy
import asyncio
from loguru import logger
from typing import List, Dict, Any, Tuple
from pydantic import BaseModel
from langgraph.types import Command
from langgraph.prebuilt.tool_node import ToolCallRequest
from langchain.agents import AgentState, create_agent
from langchain.agents.middleware import wrap_tool_call
from langchain_core.messages import BaseMessage, AIMessage, ToolMessage, AIMessageChunk, SystemMessage

from agentchat.core.callbacks import usage_metadata_callback
from agentchat.tools import WorkSpacePlugins
from agentchat.schema.usage_stats import UsageStatsAgentType
from agentchat.schema.workspace import WorkSpaceAgents
from agentchat.api.services.tool import ToolService
from agentchat.services.mcp.manager import MCPManager
from agentchat.prompts.completion import GenerateTitlePrompt
from agentchat.utils.convert import convert_mcp_config
from agentchat.core.models.manager import ModelManager
from agentchat.api.services.mcp_user_config import MCPUserConfigService
from agentchat.api.services.usage_stats import UsageStatsService
from agentchat.api.services.workspace_session import WorkSpaceSessionService
from agentchat.database.models.workspace_session import WorkSpaceSessionCreate, WorkSpaceSessionContext
from agentchat.services.memory.client import memory_client


class MCPConfig(BaseModel):
    url: str
    type: str = "sse"
    tools: List[str] = []
    server_name: str
    mcp_server_id: str


class WorkSpaceSimpleAgent:
    """

    Sub-agent that can invoke **both user-provided plugin functions and MCP tools**.  It analyses the
    current conversation, decides which tool(s) should be run, performs the calls asynchronously and
    pushes progress/result events back to the main :class:`mars_agent.agent.MarsAgent`.

    Responsibilities
    ---------------
    1. Select appropriate plugin or MCP tool according to conversation context.
    2. Execute the tool in an asynchronous, non-blocking way.
    3. Report every progress, success or error through the shared ``EventManager``.
    4. **Does not generate any LLM response** – that task belongs to the main agent.

    Usage
    -----
    ``SimpleAgent`` instances are automatically created by.
    End-users rarely need to touch this class directly.
    """

    def __init__(self,
                 model_config,
                 user_id: str,
                 session_id: str,
                 plugins: List[str] = [],
                 mcp_configs: List[MCPConfig] = []):

        # Simple-agent only needs tool calling model, not conversation model
        self.model = ModelManager.get_user_model(**model_config)
        self.plugin_tools = []
        self.mcp_tools = []
        self.mcp_configs = mcp_configs
        self.tools = []
        self.mcp_manager = MCPManager(convert_mcp_config([mcp_config.model_dump() for mcp_config in mcp_configs]))
        self.plugins = plugins
        self.session_id = session_id

        self.user_id = user_id

        # Find user config by server name
        self.server_dict: dict[str, Any] = {}

        # Initialize state management
        self._initialized = False


    async def init_simple_agent(self):
        """Initialize sub-agent - with resource management"""
        try:
            if self._initialized:
                logger.info("Simple Agent already initialized")
                return
            await self.setup_mcp_tools()
            await self.setup_plugin_tools()

            self.middlewares = await self.setup_middlewares()

            self.tools = self.plugin_tools + self.mcp_tools
            self._initialized = True
            self.react_agent = self.setup_react_agent()

            logger.info("Simple Agent initialized successfully")
        except Exception as err:
            logger.error(f"Failed to initialize Simple Agent: {err}")
            raise

    @staticmethod
    def _build_provisional_title(query: str, max_length: int = 24) -> str:
        compact_query = " ".join(query.split())
        if not compact_query:
            return "新会话"
        return compact_query[:max_length]

    @staticmethod
    def _extract_tool_trace_and_answer(messages: List[BaseMessage]) -> Tuple[List[BaseMessage], str]:
        """
        从 agent 的完整消息列表中提取工具轨迹和最终自然语言答案。

        `create_agent` 在工具执行完成后通常会追加一条最终 AI 回复。
        这里优先复用那条最终回复，避免再次把同一组上下文交给模型重写，
        从而出现把工具计划文本化输出（如 `<tool_call>`）的问题。
        """
        tool_trace: List[BaseMessage] = []
        final_answer = ""

        for message in messages:
            if isinstance(message, ToolMessage) or (isinstance(message, AIMessage) and message.tool_calls):
                tool_trace.append(message)

        for message in reversed(messages):
            if isinstance(message, AIMessage) and not message.tool_calls and message.content:
                final_answer = message.content
                break

        return tool_trace, final_answer

    @staticmethod
    def _stream_text_chunks(text: str, chunk_size: int = 24):
        for index in range(0, len(text), chunk_size):
            yield text[index:index + chunk_size]

    @staticmethod
    def _track_background_task(task: asyncio.Task, task_name: str):
        def _log_task_result(completed_task: asyncio.Task):
            try:
                completed_task.result()
            except Exception as err:
                logger.warning(f"Background task `{task_name}` failed: {err}")

        task.add_done_callback(_log_task_result)

    def _build_tool_execution_messages(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        if not self.tools:
            return messages

        tool_names = ", ".join(tool.name for tool in self.tools)
        tool_prompt = SystemMessage(content=(
            "你正在使用带工具的工作台助手。"
            "如果用户问题涉及实时信息、联网搜索、天气、论文检索、邮件、快递、图像生成或文件转换，"
            "并且当前存在匹配工具，请优先调用工具，不要只凭已有知识直接回答。"
            f"当前可用工具：{tool_names}。"
        ))
        return [tool_prompt] + messages

    def setup_react_agent(self):
        return create_agent(
            model=self.model,
            tools=self.tools,
            middleware=self.middlewares
        )

    async def setup_middlewares(self):
        @wrap_tool_call
        async def handler_call_mcp_tool(
            request: ToolCallRequest,
            handler
        ) -> ToolMessage | Command:
            if self.is_mcp_tool(request.tool_call["name"]):
                # 针对鉴权的MCP Server需要用户的单独配置，例如飞书、邮箱
                mcp_config = await MCPUserConfigService.get_mcp_user_config(self.user_id, self.get_mcp_id_by_tool(request.tool_call["name"]))
                request.tool_call["args"].update(mcp_config)
                tool_result = await handler(request)
                print(tool_result)
            else:
                tool_result = await handler(request)

            return tool_result

        return [handler_call_mcp_tool]

    async def setup_mcp_tools(self):
        """Initialize MCP tools - with error handling"""
        if not self.mcp_configs:
            self.mcp_tools = []
            return

        try:
            # Establish connection with MCP Server
            self.mcp_tools = await self.mcp_manager.get_mcp_tools()

            mcp_servers_info = await self.mcp_manager.show_mcp_tools()
            self.server_dict = {server_name: [tool["name"] for tool in tools_info] for server_name, tools_info in
                                mcp_servers_info.items()}

            logger.info(f"Loaded {len(self.mcp_tools)} MCP tools from MCP servers")

        except Exception as err:
            logger.error(f"Failed to initialize MCP tools: {err}")
            self.mcp_tools = []

    async def setup_plugin_tools(self):
        """Initialize plugin tools - with error handling"""
        try:
            tools_name = await ToolService.get_tool_name_by_id(self.plugins)
            for name in tools_name:
                self.plugin_tools.append(WorkSpacePlugins[name])

            logger.info(f"Loaded {len(self.plugin_tools)} plugin tools")

        except Exception as err:
            logger.error(f"Failed to initialize plugin tools: {err}")
            self.plugin_tools = []

    async def ainvoke(self, messages: List[BaseMessage]):
        """Sub-agent tool execution - only return tool execution results, no model reply"""
        if not self._initialized:
            await self.init_simple_agent()
        tool_ready_messages = self._build_tool_execution_messages(messages)

        try:
            react_agent_task = None
            if self.tools and len(self.tools) != 0:
                react_agent_task = asyncio.create_task(self.react_agent.ainvoke({"messages": tool_ready_messages}))

            # Wait for tool execution to complete
            if react_agent_task:
                results = await react_agent_task
                messages = results["messages"][:-1]  # Remove messages that didn't hit tools

                messages = [msg for msg in messages if
                            isinstance(msg, ToolMessage) or (isinstance(msg, AIMessage) and msg.tool_calls)]

                return messages
            else:
                return []

        except Exception as err:
            return []

    async def _generate_title(self, query):
        session = await WorkSpaceSessionService.get_workspace_session_from_id(self.session_id, self.user_id)
        if session:
            return session.get("title")
        title_prompt = GenerateTitlePrompt.format(query=query)
        response = await self.model.ainvoke(title_prompt, config={"callbacks": [usage_metadata_callback]})
        return response.content

    async def _persist_workspace_session_context(self, contexts: WorkSpaceSessionContext) -> bool:
        session = await WorkSpaceSessionService.get_workspace_session_from_id(self.session_id, self.user_id)
        if session:
            await WorkSpaceSessionService.update_workspace_session_contexts(
                session_id=self.session_id,
                session_context=contexts.model_dump()
            )
            return False

        await WorkSpaceSessionService.create_workspace_session(
            WorkSpaceSessionCreate(
                title=self._build_provisional_title(contexts.query),
                user_id=self.user_id,
                session_id=self.session_id,
                contexts=[contexts.model_dump()],
                agent=WorkSpaceAgents.SimpleAgent.value,
            )
        )
        return True

    async def _finalize_workspace_response(self, query: str, final_answer: str, should_update_title: bool):
        if should_update_title:
            try:
                title = await self._generate_title(query)
                if title:
                    await WorkSpaceSessionService.update_workspace_session_title(self.session_id, title)
            except Exception as err:
                logger.warning(f"Failed to update workspace title in background: {err}")

        try:
            await memory_client.add(
                user_id=self.user_id,
                run_id=self.session_id,
                messages=[
                    {"role": "user", "content": query},
                    {"role": "assistant", "content": final_answer},
                ],
            )
        except Exception as err:
            logger.warning(f"Failed to persist workspace long-term memory: {err}")

    async def astream(self, messages: List[BaseMessage]):
        if not self._initialized:
            await self.init_simple_agent()
        user_messages = copy.deepcopy(messages)
        tool_ready_messages = self._build_tool_execution_messages(messages)
        tool_trace_messages: List[BaseMessage] = []
        final_answer = ""
        try:
            react_agent_task = None
            if self.tools and len(self.tools) != 0:
                react_agent_task = asyncio.create_task(self.react_agent.ainvoke(input={"messages": tool_ready_messages}, config={"callbacks": [usage_metadata_callback]}))

            # Wait for tool execution to complete
            if react_agent_task:
                results = await react_agent_task
                tool_trace_messages, final_answer = self._extract_tool_trace_and_answer(results["messages"])
        except Exception as err:
            raise ValueError from err

        # 优先复用 agent 自己已经产出的最终答案，避免二次生成时把工具计划误输出为普通文本。
        if final_answer:
            for text_chunk in self._stream_text_chunks(final_answer):
                yield {
                    "event": "task_result",
                    "data": {
                        "message": text_chunk
                    }
                }
        else:
            final_stage_guard = SystemMessage(content=(
                "你现在处于最终答复阶段。"
                "不要输出任何工具调用标记、函数调用 XML/JSON 或伪代码，"
                "例如 `<tool_call>`、`<function=...>`、`<parameter=...>`。"
                "如果当前没有可用工具，请直接说明限制，或向用户索取缺失的关键信息。"
                "如果已经有工具结果，请只基于已有结果给出自然语言答案。"
            ))
            answer_messages = [final_stage_guard] + user_messages + tool_trace_messages
            async for chunk in self.model.astream(input=answer_messages, config={"callbacks": [usage_metadata_callback]}):
                if not chunk.content:
                    continue
                yield {
                    "event": "task_result",
                    "data":{
                        "message": chunk.content
                    }
                }
                final_answer += chunk.content

        session_created = await self._persist_workspace_session_context(
            WorkSpaceSessionContext(
                query=user_messages[-1].content,
                answer=final_answer,
            )
        )

        background_task = asyncio.create_task(
            self._finalize_workspace_response(
                query=user_messages[-1].content,
                final_answer=final_answer,
                should_update_title=session_created,
            )
        )
        self._track_background_task(background_task, "workspace_response_finalize")

        yield {
            "event": "task_complete",
            "data": {
                "session_id": self.session_id
            }
        }


    async def _record_agent_token_usage(self, response: AIMessage | AIMessageChunk | BaseMessage, model):
        if response.usage_metadata:
            await UsageStatsService.create_usage_stats(
                model=model,
                user_id=self.user_id,
                agent=UsageStatsAgentType.simple_agent,
                input_tokens=response.usage_metadata.get("input_tokens"),
                output_tokens=response.usage_metadata.get("output_tokens")
            )

    def is_mcp_tool(self, tool_name: str):
        """Determine if it's an MCP tool and return the corresponding tool instance"""
        mcp_names = [tool.name for tool in self.mcp_tools]
        plugin_names = [tool.name for tool in self.plugin_tools]

        if tool_name in mcp_names:
            return True
        elif tool_name in plugin_names:
            return False
        else:
            raise ValueError(f"Tool '{tool_name}' not found in either MCP or plugin tools.")

    def get_mcp_id_by_tool(self, tool_name):
        for server_name, tools in self.server_dict.items():
            if tool_name in tools:
                for config in self.mcp_configs:
                    if server_name == config.server_name:
                        return config.mcp_server_id
        return None

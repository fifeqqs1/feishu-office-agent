# Feishu Multi-Agent Assistant

Feishu Multi-Agent Assistant 是一个面向飞书办公场景的多智能体助手平台，基于 OmniAgent 改造而来。它把对话式 AI、多 Agent 工作区、RAG 知识库、工具调用、MCP 扩展和飞书 OpenAPI 能力整合到一套 Web 应用里，适合用来搭建企业内部的办公自动化助手、知识库问答助手和任务规划型 Agent。

项目包含一个 FastAPI 后端、一个 Vue 3 前端，以及内置的 Lark/Feishu MCP 工具服务。后端负责模型编排、会话、知识库、工具和 MCP 管理；前端提供工作区、聊天、知识库、模型、工具、数据看板等可视化页面。

## 功能亮点

- 多 Agent 工作区：支持任务拆解、执行过程展示、工作区会话和任务图。
- 飞书 MCP 工具：封装飞书消息、日历、日程、文档、文件夹和用户信息接口。
- RAG 知识库：支持文档解析、切块、向量化、检索、重排和知识库文件管理。
- 多模型配置：区分对话模型、工具调用模型、推理模型、视觉模型、Embedding 和 Rerank 模型。
- 工具中心：内置天气、搜索、快递查询、文生图、Arxiv 等工具扩展入口。
- 后台管理：提供智能体、模型、工具、MCP Server、用户和使用统计等管理页面。
- 可视化前端：Vue 3 + Vite + TypeScript + Element Plus，适合二次开发。

## 架构概览

核心模块：

- `src/backend/agentchat`：FastAPI 主服务，包含 API、Agent、RAG、MCP、工具、存储和数据库逻辑。
- `src/backend/agentchat/mcp_servers/lark_mcp`：飞书/Lark MCP Server 和工具实现。
- `src/frontend`：Vue 3 前端应用。

## 技术栈

- Backend：Python 3.12、FastAPI、SQLModel、LangChain、MCP、Redis、MySQL/MariaDB
- RAG：ChromaDB / Milvus、Elasticsearch、Embedding、Rerank
- Storage：MinIO / 阿里云 OSS
- Frontend：Vue 3、Vite、TypeScript、Pinia、Element Plus、ECharts
- Feishu/Lark：lark-oapi、飞书 OpenAPI、MCP Server

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/fifeqqs1/Feishu-Multi-Agent-Assistant.git
cd Feishu-Multi-Agent-Assistant
```

### 2. 准备基础服务

后端默认依赖这些服务：

- MySQL 或 MariaDB
- Redis
- MinIO 或阿里云 OSS
- ChromaDB 或 Milvus，按你的 RAG 配置选择
- 可选：Elasticsearch、Langfuse

至少需要先创建数据库：

```sql
CREATE DATABASE agentchat DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 3. 配置后端


```bash
cp src/backend/agentchat/config.example.yaml src/backend/agentchat/config.yaml
```

然后编辑 `src/backend/agentchat/config.yaml`，填入你自己的数据库、Redis、模型 API Key、飞书应用信息、对象存储等配置。

注意：`config.yaml`、`config_ceshi.yaml`、`.env`、本地数据库和向量库文件都已加入 `.gitignore`，不要把真实密钥提交到公开仓库。

### 4. 启动后端

推荐使用 Poetry：

```bash
poetry install
cd src/backend
poetry run uvicorn agentchat.main:app --host 0.0.0.0 --port 7860
```

如果使用 `venv + pip`：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd src/backend
uvicorn agentchat.main:app --host 0.0.0.0 --port 7860
```

健康检查：

```bash
curl http://localhost:7860/health
```

### 5. 启动前端

```bash
cd src/frontend
npm install
npm run dev -- --host 0.0.0.0 --port 8090
```

默认访问：

- 前端：`http://localhost:8090`
- 后端：`http://localhost:7860`

前端开发代理会把 `/api` 请求转发到后端服务，配置见 `src/frontend/vite.config.ts`。

## 飞书 MCP 工具

内置 MCP Server 位于 `src/backend/agentchat/mcp_servers/lark_mcp`，当前封装的飞书能力包括：

- 用户信息：批量查询用户 ID 和用户详情
- 消息：发送文本或富文本消息
- 日历：创建、查询、更新、删除日历
- 日程：创建、查询、更新、删除日程，添加参会者
- 文档：创建文档、读取文档内容
- 文件夹：创建文件夹、列出文件夹文件

单独调试 MCP Server：

```bash
cd src/backend/agentchat/mcp_servers/lark_mcp
poetry install
poetry run python -m lark_mcp.main --transport sse
```

飞书应用需要在飞书开放平台创建，并开通对应 OpenAPI 权限。真实的 `app_id` 和 `app_secret` 建议通过用户配置或本地配置传入，不要写进源码。

## 配置说明

主要配置文件是 `src/backend/agentchat/config.yaml`，字段结构可参考 `src/backend/agentchat/config.example.yaml`。

| 配置块 | 作用 |
| --- | --- |
| `server` | 后端监听地址、端口、项目名称和版本 |
| `mysql` | 同步和异步数据库连接 |
| `redis` | Redis 连接 |
| `multi_models` | 对话、工具调用、推理、视觉、Embedding、Rerank 模型 |
| `tools` | 天气、搜索、快递等外部工具 API |
| `rag` | 文档切分、检索、向量库和 Elasticsearch 配置 |
| `storage` | MinIO 或 OSS 对象存储 |
| `wechat_config` | 微信相关配置 |
| `langfuse` | 链路追踪配置 |
| `whitelist_paths` | 登录等无需鉴权的 API 白名单 |

## 目录结构

```text
.
├── scripts/
├── src/
│   ├── backend/
│   │   ├── agentchat/
│   │   │   ├── api/
│   │   │   ├── core/
│   │   │   ├── database/
│   │   │   ├── mcp_servers/
│   │   │   ├── services/
│   │   │   ├── tools/
│   │   │   ├── config.example.yaml
│   │   │   └── main.py
│   │   └── fastapi_jwt_auth/
│   └── frontend/
│       ├── src/
│       ├── package.json
│       └── vite.config.ts
├── pyproject.toml
├── requirements.txt
└── README.md
```

## 开发命令

后端格式和基础检查可按需添加到项目脚本中，目前常用命令：

```bash
# Backend
cd src/backend
uvicorn agentchat.main:app --reload --host 0.0.0.0 --port 7860

# Frontend
cd src/frontend
npm run dev
npm run build
npm run lint
```

## License

本项目使用 [MIT License](./LICENSE)。

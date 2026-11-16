# Assistant

基于火山引擎 veADK（Agent Development Kit）构建的智能个人助手 Agent。

## 功能特性

- **记忆系统**：短期记忆（会话级内存）+ 长期记忆（火山引擎 VikingDB 向量数据库持久化）
- **知识库检索**：基于 VikingDB 的 RAG 知识库
- **内置工具**：代码沙箱执行（run_code）、MCP 工具路由、Skills 执行、联网搜索（web_search）
- **飞书集成**：搜索飞书文档、读取飞书文档内容（见 lark_tools.py，使用 lark-oapi SDK 自动管理 token）

## 项目结构

| 文件 | 说明 |
|---|---|
| `agent.py` | 核心 Agent 定义（记忆、知识库、工具集），含本地调试 CLI 入口 |
| `agentkit-agent.py` | AgentKit 云端部署入口（HTTP 服务，entry_point） |
| `agentkit.yaml` | AgentKit 云端部署配置 |
| `lark_tools.py` | 飞书文档搜索与读取工具 |
| `test_lark_tools.py` | 飞书工具单元测试（pytest，mock，无真实网络请求） |
| `Dockerfile` | 容器化构建配置 |
| `requirements.txt` | Python 依赖（已锁定版本） |

## 环境变量

通过 `.env` 或 AgentKit `runtime_envs` 配置（未配置的可选项会自动降级，不会导致启动失败）：

| 变量 | 必需 | 说明 |
|---|---|---|
| `FEISHU_APP_ID` / `FEISHU_APP_SECRET` | 否 | 飞书应用凭证，缺失时飞书工具返回提示信息 |
| `DATABASE_VIKINGMEM_COLLECTION` | 否 | VikingDB 长期记忆 collection，缺失则无长期记忆 |
| `DATABASE_VIKING_COLLECTION` | 否 | VikingDB 知识库 collection，缺失则无知识库 |
| `SKILL_SPACE_ID` | 否 | Skills 空间 ID |
| `MODEL_AGENT_NAME` / `MODEL_AGENT_API_KEY` | 是 | 云端由 AgentKit runtime_envs 注入 |

## 本地调试

```bash
pip install -r requirements.txt
python agent.py
```

## 运行测试

```bash
python -m pytest test_lark_tools.py -v
```

## 云端部署

通过 AgentKit 部署到火山引擎，入口与配置见 `agentkit.yaml`（`entry_point: agentkit-agent.py`）。

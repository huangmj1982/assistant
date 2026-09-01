# Assistant

基于火山引擎 veADK（Agent Development Kit）构建的智能个人助手 Agent。

## 功能特性

- **记忆系统**：短期记忆（会话级内存）+ 长期记忆（火山引擎 VikingDB 向量数据库持久化）
- **知识库检索**：基于 VikingDB 的 RAG 知识库
- **内置工具**：代码沙箱执行（run_code）、MCP 工具路由、Skills 执行、联网搜索（web_search）
- **飞书集成**：搜索飞书文档、读取飞书文档内容（见 lark_tools.py）

## 项目结构

| 文件 | 说明 |
|---|---|
| `agent.py` | 核心 Agent 定义（记忆、知识库、工具集），含本地调试 CLI 入口 |
| `assistant.py` | 基于 AgentkitSimpleApp 的 SSE 流式服务入口 |
| `agentkit-agent.py` | AgentKit 标准部署入口 |
| `agentkit.yaml` | AgentKit 云端部署配置 |
| `lark_tools.py` | 飞书文档搜索与读取工具 |
| `Dockerfile` | 容器化构建配置 |
| `requirements.txt` | Python 依赖 |

## 本地调试

```bash
pip install -r requirements.txt
python agent.py
```

## 云端部署

通过 AgentKit 部署到火山引擎，配置见 `agentkit.yaml`。

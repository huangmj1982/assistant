# Proposal

## Why

当前目录已经包含个人助手的主要实现，但缺少统一、可评审的行为规格与验收标准。需要将这些能力整理为一个完整变更，明确对话、记忆、知识检索、工具集成和部署行为，为后续实施与回归验证提供依据。

## What Changes

- 定义基于 veADK 的个人助手对话行为，以及代码沙箱、MCP、Skills 和联网搜索工具的使用方式。
- 定义会话级短期记忆与基于 VikingDB 的可选长期记忆，并明确未配置长期记忆时的降级行为。
- 定义基于 VikingDB 的可选知识库检索能力。
- 定义飞书文档搜索与内容读取能力，包括凭证缺失和接口失败时的可理解反馈。
- 定义本地调试入口、AgentKit HTTP 部署入口和健康检查行为。
- 补充覆盖核心行为和可选集成降级的验证任务，不改变现有对外接口。

## Capabilities

### New Capabilities

- `assistant-conversation`: 个人助手的自然语言对话、工具选择与响应行为。
- `assistant-memory`: 会话短期记忆、长期记忆持久化及可选能力降级。
- `knowledge-retrieval`: 基于 VikingDB 的知识库检索及未配置时的降级。
- `lark-document-access`: 飞书文档搜索、文档内容读取和错误反馈。
- `assistant-deployment`: 本地运行、AgentKit 请求处理、健康检查与运行配置。

### Modified Capabilities

无。

## Impact

- 影响 `agent.py` 中的 Agent、记忆、知识库和工具配置。
- 影响 `lark_tools.py` 中的飞书文档工具及其单元测试。
- 影响 `agentkit-agent.py`、`agentkit.yaml`、`Dockerfile` 和 `requirements.txt` 所定义的运行与部署链路。
- 依赖 veADK、VikingDB、飞书开放平台及 AgentKit；可选外部能力未配置时不得影响助手核心对话功能。

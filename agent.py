import asyncio
import logging
import os

from veadk import Agent, Runner  # 导入veADK定义智能体的核心类和运行器
from veadk.knowledgebase import KnowledgeBase  # 导入知识库组件，可以存储和检索文档知识
from veadk.memory import LongTermMemory, ShortTermMemory  # 导入记忆组件
from google.adk.agents.callback_context import CallbackContext  # 导入call_back函数
from dotenv import load_dotenv

try:
    from .lark_tools import search_lark_docs_tool, get_lark_doc_content_tool  # 包方式导入
except ImportError:
    from lark_tools import search_lark_docs_tool, get_lark_doc_content_tool  # 顶层模块导入

logger = logging.getLogger(__name__)

dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(dotenv_path=dotenv_path)

_agent = None
_short_term_memory = None


def _build_agent():
    """延迟构建 Agent 及其依赖资源。

    将环境变量校验与 Viking 记忆/知识库的初始化推迟到首次使用时，
    避免仅 import 本模块（如被 __init__ 或工具链引用）就因缺少环境变量而失败。
    """
    global _agent, _short_term_memory
    if _agent is not None:
        return _agent

    memory_name = os.getenv("DATABASE_VIKINGMEM_COLLECTION")
    if not memory_name:
        raise ValueError("DATABASE_VIKINGMEM_COLLECTION environment variable is not set")

    knowledge_name = os.getenv("DATABASE_VIKING_COLLECTION")
    if not knowledge_name:
        raise ValueError("DATABASE_VIKING_COLLECTION environment variable is not set")

    # 使用viking作为长期记忆存储，可按需切换 mem0
    long_term_memory = LongTermMemory(backend="viking", index=memory_name)

    # 使用本地内存作为短期记忆，如需持久化backend可配置为mysql，需提前在火山创建数据库
    _short_term_memory = ShortTermMemory(backend="local")

    # 使用viking作为知识库存储
    knowledgebase = KnowledgeBase(backend="viking", index=knowledge_name)

    # 定义异步回调函数，用于在代理执行完成后获取当前会话并将其添加到长期记忆存储中
    async def after_agent_execution(callback_context: CallbackContext):
        # veADK 未暴露公开的 session 访问接口，这里通过私有属性获取并做防御性判断
        invocation_context = getattr(callback_context, "_invocation_context", None)
        session = getattr(invocation_context, "session", None)
        if session is None:
            logger.warning("无法从 callback_context 获取 session，跳过长期记忆写入")
            return
        await long_term_memory.add_session_to_memory(session)

    # 获取 SKILL_SPACE_ID
    skill_space_id = os.getenv("SKILL_SPACE_ID")

    # 内置工具在 import 期会校验环境变量（如 TOOL_MCP_ROUTER_URL），故延迟到此处置入
    from veadk.tools.builtin_tools.run_code import run_code  # 代码沙箱工具
    from veadk.tools.builtin_tools.mcp_router import mcp_router  # MCP工具集
    from veadk.tools.builtin_tools.execute_skills import execute_skills  # Skills执行工具
    from veadk.tools.builtin_tools.web_search import web_search  # 联网搜索工具

    # 定义个人助手Agent
    _agent = Agent(
        name="personal_assistant",
        description="一个智能个人助手，可以帮助用户管理日常事务和提供信息。",
        instruction="""你是一个友好的智能个人助手，请用简洁明了的语言回答用户的问题。
如果用户询问与知识库相关的信息，请使用知识库检索。
如果用户提到个人偏好或重要信息，请将其存储到长期记忆中。
如果需要执行代码生成任务，请使用代码沙箱工具。
如果用户需要使用Skills完成特定任务，请使用 execute_skills 工具执行相应的Skills。
如果用户提到或询问飞书文档、表格、多维表格或知识库内容，请使用以下工具：
1. 如果用户要搜索飞书文档，请使用 search_lark_docs 工具，传入搜索关键词
2. 如果用户要读取特定飞书文档的内容，请使用 get_lark_doc_content 工具，传入文档ID
3. 搜索文档时，用户可以提供关键词（如"极氪 链路梳理"），工具会返回相关文档
4. 读取文档内容时，需要从文档链接中提取文档ID（链接最后一部分）
如果用户询问实时信息、最新新闻、天气、需要联网查询的问题或知识库中没有的信息，请使用 web_search 工具进行联网搜索。""",
        short_term_memory=_short_term_memory,
        long_term_memory=long_term_memory,
        knowledgebase=knowledgebase,
        skills=[skill_space_id] if skill_space_id else [],
        tools=[run_code, mcp_router, execute_skills, search_lark_docs_tool, get_lark_doc_content_tool, web_search],
        after_agent_callback=after_agent_execution,
    )
    return _agent


def __getattr__(name):
    # 惰性暴露 agent：兼容 `from agent import personal_assistant` 与 veadk web 的 root_agent 发现
    if name in ("personal_assistant", "root_agent"):
        return _build_agent()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted([*globals(), "personal_assistant", "root_agent"])


async def main():
    """运行个人助手的主函数"""
    print("欢迎使用智能个人助手！")
    print("输入 'exit' 或 'quit' 退出程序。")
    print("=" * 60)

    personal_assistant = _build_agent()

    # 创建智能体运行器
    runner = Runner(
        agent=personal_assistant,
        app_name="personal_assistant_demo",
        user_id="demo_user",
        short_term_memory=_short_term_memory,
    )

    while True:
        user_input = input("请输入您的问题:  ")

        if user_input.lower() in ["exit", "quit", "退出"]:
            print("再见！")
            break

        try:
            # 运行agent并获取响应
            response = await runner.run(messages=user_input)
            print(f"助手: {response}")
        except Exception as e:
            print(f"发生错误: {e}")

        print("=" * 120)


if __name__ == "__main__":
    asyncio.run(main())

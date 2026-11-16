"""Agent 配置与记忆行为测试；所有外部依赖均使用 mock。"""
import asyncio
import importlib.util
import logging
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parent


class _FakeLongTermMemory:
    instances = []
    fail = False

    def __init__(self, backend, index):
        self.backend = backend
        self.index = index
        self.sessions = []
        type(self).instances.append(self)

    async def add_session_to_memory(self, session):
        if type(self).fail:
            raise RuntimeError("memory backend unavailable")
        self.sessions.append(session)


class _FakeKnowledgeBase:
    def __init__(self, backend, index):
        self.backend = backend
        self.index = index


class _FakeShortTermMemory:
    def __init__(self, backend):
        self.backend = backend


class _FakeAgent:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def _load_agent(
    monkeypatch, *, mcp_available=True, configured=False, model_configured=True, model_env=None
):
    optional_envs = (
        "DATABASE_VIKINGMEM_COLLECTION",
        "DATABASE_VIKING_COLLECTION",
        "SKILL_SPACE_ID",
        "MODEL_AGENT_NAME",
        "MODEL_AGENT_API_KEY",
    )
    for name in optional_envs:
        monkeypatch.delenv(name, raising=False)
    if model_configured:
        monkeypatch.setenv("MODEL_AGENT_NAME", "test-model")
        monkeypatch.setenv("MODEL_AGENT_API_KEY", "test-api-key")
    for name, value in (model_env or {}).items():
        monkeypatch.setenv(name, value)
    if configured:
        monkeypatch.setenv("DATABASE_VIKINGMEM_COLLECTION", "memory-collection")
        monkeypatch.setenv("DATABASE_VIKING_COLLECTION", "knowledge-collection")
        monkeypatch.setenv("SKILL_SPACE_ID", "skill-space")

    _FakeLongTermMemory.instances = []
    _FakeLongTermMemory.fail = False

    tools = {
        name: object()
        for name in (
            "run_code",
            "execute_skills",
            "web_search",
            "mcp_router",
            "search_lark_docs_tool",
            "get_lark_doc_content_tool",
        )
    }

    veadk = types.ModuleType("veadk")
    veadk.Agent = _FakeAgent
    veadk.Runner = object
    knowledgebase = types.ModuleType("veadk.knowledgebase")
    knowledgebase.KnowledgeBase = _FakeKnowledgeBase
    memory = types.ModuleType("veadk.memory")
    memory.LongTermMemory = _FakeLongTermMemory
    memory.ShortTermMemory = _FakeShortTermMemory

    module_names = {
        "veadk": veadk,
        "veadk.knowledgebase": knowledgebase,
        "veadk.memory": memory,
    }
    for module_name, attr in (
        ("veadk.tools.builtin_tools.run_code", "run_code"),
        ("veadk.tools.builtin_tools.execute_skills", "execute_skills"),
        ("veadk.tools.builtin_tools.web_search", "web_search"),
        ("veadk.tools.builtin_tools.mcp_router", "mcp_router"),
    ):
        module = types.ModuleType(module_name)
        setattr(module, attr, tools[attr])
        module_names[module_name] = module

    callback_context = types.ModuleType("google.adk.agents.callback_context")
    callback_context.CallbackContext = object
    module_names["google.adk.agents.callback_context"] = callback_context

    dotenv = types.ModuleType("dotenv")
    dotenv.load_dotenv = lambda **kwargs: None
    module_names["dotenv"] = dotenv

    lark_tools = types.ModuleType("lark_tools")
    lark_tools.search_lark_docs_tool = tools["search_lark_docs_tool"]
    lark_tools.get_lark_doc_content_tool = tools["get_lark_doc_content_tool"]
    module_names["lark_tools"] = lark_tools

    for name, module in module_names.items():
        monkeypatch.setitem(sys.modules, name, module)
    if not mcp_available:
        monkeypatch.setitem(sys.modules, "veadk.tools.builtin_tools.mcp_router", None)

    spec = importlib.util.spec_from_file_location(f"_agent_under_test_{id(monkeypatch)}", ROOT / "agent.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module._test_tools = tools
    return module


@pytest.mark.parametrize(
    "model_env",
    [
        {},
        {"MODEL_AGENT_NAME": "test-model"},
        {"MODEL_AGENT_API_KEY": "test-api-key"},
    ],
)
def test_agent_requires_model_configuration(monkeypatch, model_env):
    with pytest.raises(RuntimeError, match="缺少必需模型配置") as exc_info:
        _load_agent(monkeypatch, model_configured=False, model_env=model_env)

    for name in ("MODEL_AGENT_NAME", "MODEL_AGENT_API_KEY"):
        if name not in model_env:
            assert name in str(exc_info.value)


def test_agent_without_optional_config_degrades_cleanly(monkeypatch, capsys):
    module = _load_agent(monkeypatch, mcp_available=False)

    assistant = module.personal_assistant
    assert assistant.long_term_memory is None
    assert assistant.knowledgebase is None
    assert assistant.skills == []
    assert module._test_tools["mcp_router"] not in assistant.tools
    assert module._test_tools["run_code"] in assistant.tools
    assert module._test_tools["web_search"] in assistant.tools

    output = capsys.readouterr().out
    assert "长期记忆功能不可用" in output
    assert "知识库检索功能不可用" in output
    assert "MCP 工具路由功能已跳过" in output


def test_agent_registers_configured_integrations_and_tool_instructions(monkeypatch):
    module = _load_agent(monkeypatch, configured=True)

    assistant = module.personal_assistant
    assert assistant.long_term_memory.index == "memory-collection"
    assert assistant.knowledgebase.index == "knowledge-collection"
    assert assistant.skills == ["skill-space"]
    assert module._test_tools["mcp_router"] in assistant.tools
    for phrase in ("代码沙箱", "execute_skills", "web_search", "知识库检索"):
        assert phrase in assistant.instruction


@pytest.mark.parametrize("command", ["exit", "quit", "退出"])
def test_main_exits_on_command(monkeypatch, capsys, command):
    module = _load_agent(monkeypatch)

    class FakeRunner:
        def __init__(self, **kwargs):
            pass

        async def run(self, messages):
            pytest.fail("退出命令不应调用模型")

    monkeypatch.setattr(module, "Runner", FakeRunner)
    monkeypatch.setattr("builtins.input", lambda _: command)

    asyncio.run(module.main())

    assert "再见！" in capsys.readouterr().out


def test_after_agent_execution_skips_disabled_long_term_memory(monkeypatch):
    module = _load_agent(monkeypatch)
    context = SimpleNamespace(session=object())

    asyncio.run(module.after_agent_execution(context))


def test_after_agent_execution_persists_session(monkeypatch):
    module = _load_agent(monkeypatch)
    memory = _FakeLongTermMemory(backend="viking", index="memory")
    module.long_term_memory = memory
    context = SimpleNamespace(session=object())

    asyncio.run(module.after_agent_execution(context))

    assert memory.sessions == [context.session]


def test_after_agent_execution_logs_memory_failure(monkeypatch, caplog):
    module = _load_agent(monkeypatch)
    memory = _FakeLongTermMemory(backend="viking", index="memory")
    module.long_term_memory = memory
    _FakeLongTermMemory.fail = True
    context = SimpleNamespace(session=object())

    with caplog.at_level(logging.ERROR):
        asyncio.run(module.after_agent_execution(context))

    assert "写入长期记忆失败" in caplog.text
    assert "memory backend unavailable" in caplog.text

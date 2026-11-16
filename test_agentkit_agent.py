"""AgentKit 入口测试；Agent、Runner 与 App 均使用 mock。"""
import asyncio
import importlib.util
import sys
import types
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent


class _FakeRunner:
    instances = []

    def __init__(self, agent):
        self.agent = agent
        self.calls = []
        type(self).instances.append(self)

    async def run(self, **kwargs):
        self.calls.append(kwargs)
        return "助手响应"


class _FakeApp:
    def entrypoint(self, func):
        return func

    def ping(self, func):
        return func

    def run(self, **kwargs):
        pass


def _load_entrypoint(monkeypatch):
    _FakeRunner.instances = []

    agent = types.ModuleType("agent")
    agent.personal_assistant = object()
    veadk = types.ModuleType("veadk")
    veadk.Runner = _FakeRunner
    apps = types.ModuleType("agentkit.apps")
    apps.AgentkitSimpleApp = _FakeApp

    monkeypatch.setitem(sys.modules, "agent", agent)
    monkeypatch.setitem(sys.modules, "veadk", veadk)
    monkeypatch.setitem(sys.modules, "agentkit.apps", apps)

    spec = importlib.util.spec_from_file_location(
        f"_agentkit_entrypoint_{id(monkeypatch)}",
        ROOT / "agentkit-agent.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("missing_field", ["prompt", "user_id", "session_id"])
def test_run_rejects_missing_required_field(monkeypatch, missing_field):
    module = _load_entrypoint(monkeypatch)
    payload = {"prompt": "你好"}
    headers = {"user_id": "user-1", "session_id": "session-1"}
    if missing_field == "prompt":
        del payload[missing_field]
    else:
        del headers[missing_field]

    with pytest.raises(ValueError, match=missing_field):
        asyncio.run(module.run(payload, headers))

    assert module.runner.calls == []


def test_run_passes_identity_session_and_returns_text(monkeypatch):
    module = _load_entrypoint(monkeypatch)

    result = asyncio.run(
        module.run(
            {"prompt": "你好"},
            {"user_id": "user-1", "session_id": "session-1"},
        )
    )

    assert result == "助手响应"
    assert module.runner.calls == [
        {
            "messages": "你好",
            "user_id": "user-1",
            "session_id": "session-1",
        }
    ]


def test_ping_returns_pong(monkeypatch):
    module = _load_entrypoint(monkeypatch)

    assert module.ping() == "pong!"

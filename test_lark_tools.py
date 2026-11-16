"""lark_tools 单元测试：使用 mock 的 lark_oapi，不发起真实网络请求、不依赖凭证。"""
import asyncio
import json
import sys
import types
from unittest import mock

import pytest

import lark_tools as lt
from lark_tools import LarkDocTools


class _FakeBuilder:
    """通用链式 builder，所有设置方法返回自身，build() 返回预置对象。"""

    def __init__(self, built):
        self._built = built
        self.calls = []

    def __getattr__(self, name):
        if name == "build":
            return lambda: self._built

        def _record(*args, **kwargs):
            self.calls.append((name, args))
            return self

        return _record


class _FakeResponse:
    def __init__(self, success, data=None, code=0, msg="ok", log_id="log-1"):
        self._success = success
        self.data = data
        self.code = code
        self.msg = msg
        self._log_id = log_id

    def success(self):
        return self._success

    def get_log_id(self):
        return self._log_id


def _install_fake_lark(monkeypatch, response, captured):
    """构造并注入一个假的 lark_oapi 模块到 sys.modules。"""
    fake = types.ModuleType("lark_oapi")

    class _LogLevel:
        WARNING = "warning"
        INFO = "info"

    fake.LogLevel = _LogLevel
    fake.JSON = types.SimpleNamespace(marshal=lambda data, indent=4: json.dumps(data, ensure_ascii=False))

    fake_client = mock.MagicMock()
    fake_client.search.v2.doc_wiki.search.return_value = response
    fake_client.docx.v1.document.raw_content.return_value = response
    captured["client"] = fake_client

    client_builder = _FakeBuilder(fake_client)

    class _Client:
        @staticmethod
        def builder():
            return client_builder

    fake.Client = _Client

    # search.v2 子模块
    search_v2 = types.ModuleType("lark_oapi.api.search.v2")

    class _ReqBody:
        @staticmethod
        def builder():
            return _FakeBuilder(("body",))

    class _Req:
        @staticmethod
        def builder():
            return _FakeBuilder(("req",))

    search_v2.SearchDocWikiRequestBody = _ReqBody
    search_v2.SearchDocWikiRequest = _Req

    # docx.v1 子模块
    docx_v1 = types.ModuleType("lark_oapi.api.docx.v1")

    class _RawReq:
        @staticmethod
        def builder():
            return _FakeBuilder(("raw",))

    docx_v1.RawContentDocumentRequest = _RawReq

    api_mod = types.ModuleType("lark_oapi.api")
    search_pkg = types.ModuleType("lark_oapi.api.search")
    docx_pkg = types.ModuleType("lark_oapi.api.docx")

    monkeypatch.setitem(sys.modules, "lark_oapi", fake)
    monkeypatch.setitem(sys.modules, "lark_oapi.api", api_mod)
    monkeypatch.setitem(sys.modules, "lark_oapi.api.search", search_pkg)
    monkeypatch.setitem(sys.modules, "lark_oapi.api.search.v2", search_v2)
    monkeypatch.setitem(sys.modules, "lark_oapi.api.docx", docx_pkg)
    monkeypatch.setitem(sys.modules, "lark_oapi.api.docx.v1", docx_v1)

    return fake_client, client_builder


def _make_tools(monkeypatch, app_id="cli_x", app_secret="sec_x"):
    monkeypatch.setenv("FEISHU_APP_ID", app_id)
    monkeypatch.setenv("FEISHU_APP_SECRET", app_secret)
    return LarkDocTools()


def test_module_tools_are_function_tools():
    from google.adk.tools.function_tool import FunctionTool

    assert isinstance(lt.search_lark_docs_tool, FunctionTool)
    assert isinstance(lt.get_lark_doc_content_tool, FunctionTool)


def test_missing_credentials_returns_error(monkeypatch):
    monkeypatch.delenv("FEISHU_APP_ID", raising=False)
    monkeypatch.delenv("FEISHU_APP_SECRET", raising=False)
    tools = LarkDocTools()

    result = asyncio.run(tools.search_lark_docs("关键词"))
    assert "未配置飞书应用凭证" in result

    result = asyncio.run(tools.get_lark_doc_content("doc-id"))
    assert "未配置飞书应用凭证" in result


def test_client_built_with_app_credentials_only(monkeypatch):
    tools = _make_tools(monkeypatch)
    captured = {}
    response = _FakeResponse(True, data={"items": []})
    _, builder = _install_fake_lark(monkeypatch, response, captured)

    asyncio.run(tools.search_lark_docs("测试"))

    method_names = [name for name, _ in builder.calls]
    assert "app_id" in method_names
    assert "app_secret" in method_names
    # 不应手动传入静态 token（SDK 自动管理续期）
    assert "tenant_access_token" not in method_names


def test_search_success_returns_marshaled_data(monkeypatch):
    tools = _make_tools(monkeypatch)
    captured = {}
    data = {"items": [{"title": "文档A"}], "total": 1}
    response = _FakeResponse(True, data=data)
    fake_client, _ = _install_fake_lark(monkeypatch, response, captured)

    result = asyncio.run(tools.search_lark_docs("极氪"))

    fake_client.search.v2.doc_wiki.search.assert_called_once()
    assert "文档A" in result


def test_search_failure_returns_error_message(monkeypatch):
    tools = _make_tools(monkeypatch)
    captured = {}
    response = _FakeResponse(False, code=99991663, msg="token invalid", log_id="log-err")
    _install_fake_lark(monkeypatch, response, captured)

    result = asyncio.run(tools.search_lark_docs("关键词"))

    assert "搜索失败" in result
    assert "99991663" in result


def test_get_doc_content_success(monkeypatch):
    tools = _make_tools(monkeypatch)
    captured = {}
    response = _FakeResponse(True, data={"content": "正文内容"})
    fake_client, _ = _install_fake_lark(monkeypatch, response, captured)

    result = asyncio.run(tools.get_lark_doc_content("doccn123"))

    fake_client.docx.v1.document.raw_content.assert_called_once()
    assert "正文内容" in result


def test_client_is_cached_after_first_build(monkeypatch):
    tools = _make_tools(monkeypatch)
    captured = {}
    response = _FakeResponse(True, data={"items": []})
    fake_client, _ = _install_fake_lark(monkeypatch, response, captured)

    asyncio.run(tools.search_lark_docs("a"))
    asyncio.run(tools.get_lark_doc_content("b"))

    assert tools._get_client() is tools._get_client()


# --- 2.2 文档链接提取 ---


def test_extract_document_id_from_docx_url():
    assert LarkDocTools._extract_document_id("https://xxx.feishu.cn/docx/ABCdef123") == "ABCdef123"


def test_extract_document_id_from_wiki_url():
    assert LarkDocTools._extract_document_id("https://xxx.feishu.cn/wiki/XYZtoken") == "XYZtoken"


def test_extract_document_id_passthrough_plain_id():
    assert LarkDocTools._extract_document_id("doccn123") == "doccn123"


def test_extract_document_id_rejects_empty():
    import pytest

    with pytest.raises(ValueError):
        LarkDocTools._extract_document_id("")


def test_extract_document_id_rejects_unsupported_url():
    with pytest.raises(ValueError):
        LarkDocTools._extract_document_id("https://xxx.feishu.cn/docs/ABCdef123")


def test_get_doc_content_with_url(monkeypatch):
    tools = _make_tools(monkeypatch)
    captured = {}
    response = _FakeResponse(True, data={"content": "正文"})
    fake_client, _ = _install_fake_lark(monkeypatch, response, captured)

    result = asyncio.run(tools.get_lark_doc_content("https://xxx.feishu.cn/docx/ABCdef123"))

    fake_client.docx.v1.document.raw_content.assert_called_once()
    assert "正文" in result


def test_get_doc_content_rejects_invalid_url_without_request(monkeypatch):
    tools = _make_tools(monkeypatch)
    captured = {}
    response = _FakeResponse(True, data={"content": "正文"})
    fake_client, _ = _install_fake_lark(monkeypatch, response, captured)

    result = asyncio.run(tools.get_lark_doc_content("https://xxx.feishu.cn/docs/ABCdef123"))

    assert "无效的飞书文档链接" in result
    assert "正文" not in result
    fake_client.docx.v1.document.raw_content.assert_not_called()


def test_get_doc_content_no_permission(monkeypatch):
    tools = _make_tools(monkeypatch)
    captured = {}
    response = _FakeResponse(False, code=403, msg="forbidden", log_id="log-403")
    _install_fake_lark(monkeypatch, response, captured)

    result = asyncio.run(tools.get_lark_doc_content("doccn123"))

    assert "获取文档内容失败" in result
    assert "正文" not in result


def test_get_doc_content_exception(monkeypatch):
    tools = _make_tools(monkeypatch)
    captured = {}
    response = _FakeResponse(True, data={})
    fake_client, _ = _install_fake_lark(monkeypatch, response, captured)
    fake_client.docx.v1.document.raw_content.side_effect = RuntimeError("network down")

    result = asyncio.run(tools.get_lark_doc_content("doccn123"))

    assert "获取文档内容出错" in result


# --- 2.3 敏感信息不泄露 ---


def test_secret_and_token_not_in_logs_or_response(monkeypatch, caplog):
    import logging as _logging

    secret = "super-secret-value"
    token = "t-super-secret-token"
    tools = _make_tools(monkeypatch, app_id="cli_x", app_secret=secret)
    captured = {}
    response = _FakeResponse(
        False,
        code=999,
        msg=f"err secret={secret} token={token}",
        log_id="log-x",
    )
    _install_fake_lark(monkeypatch, response, captured)

    with caplog.at_level(_logging.DEBUG):
        result = asyncio.run(tools.search_lark_docs("kw"))

    assert secret not in caplog.text
    assert secret not in result
    assert token not in caplog.text
    assert token not in result

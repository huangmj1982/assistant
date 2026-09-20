import asyncio
import json
import os

import pytest
from dotenv import load_dotenv

dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")


@pytest.fixture(autouse=True)
def _load_env():
    load_dotenv(dotenv_path=dotenv_path, override=True)


def _has_app_credentials():
    return bool(os.getenv("FEISHU_APP_ID") and os.getenv("FEISHU_APP_SECRET"))


def test_search_lark_docs_wiki_fallback(monkeypatch):
    """未配置 user token 时，降级为知识库节点标题匹配（tenant token）

    需要应用具备知识库（Wiki）只读权限；若接口因权限不可用则跳过而非误报失败。
    """
    if not _has_app_credentials():
        pytest.skip("未配置飞书凭证，跳过检索测试")

    monkeypatch.delenv("FEISHU_USER_ACCESS_TOKEN", raising=False)

    from lark_tools import LarkDocTools

    result = asyncio.run(LarkDocTools().search_lark_docs("极氪 链路梳理"))
    assert isinstance(result, str)

    if not result.lstrip().startswith("{"):
        pytest.skip(f"知识库接口不可用（可能缺少 wiki 权限）: {result}")

    payload = json.loads(result)
    assert payload["mode"] == "wiki_title"
    assert payload["keyword"] == "极氪 链路梳理"
    assert isinstance(payload["items"], list)


def test_search_lark_docs_full_text():
    """配置了 FEISHU_USER_ACCESS_TOKEN 时，走全库全文搜索

    user_access_token 有效期约 2 小时，过期后本用例会失败，需重新获取。
    """
    if not _has_app_credentials():
        pytest.skip("未配置飞书凭证，跳过检索测试")
    if not os.getenv("FEISHU_USER_ACCESS_TOKEN"):
        pytest.skip("未配置 FEISHU_USER_ACCESS_TOKEN，跳过全文搜索测试")

    from lark_tools import LarkDocTools

    result = asyncio.run(LarkDocTools().search_lark_docs("极氪 链路梳理"))
    assert isinstance(result, str)
    assert result.lstrip().startswith("{"), result

    payload = json.loads(result)
    assert payload["mode"] == "full_text", f"未走全文搜索（token 可能已过期）: {result}"
    assert isinstance(payload["items"], list)

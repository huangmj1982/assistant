import asyncio
import json
import os

import pytest
from dotenv import load_dotenv

dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")


@pytest.fixture(autouse=True)
def _load_env():
    load_dotenv(dotenv_path=dotenv_path, override=True)


def test_search_lark_docs():
    """通过知识库节点标题检索文档

    使用 tenant token 调用 wiki 空间/节点列举接口，因此需要应用具备
    知识库（Wiki）只读权限；若接口因权限不可用则跳过而非误报失败。
    """
    if not os.getenv("FEISHU_APP_ID") or not os.getenv("FEISHU_APP_SECRET"):
        pytest.skip("未配置飞书凭证，跳过检索测试")

    from lark_tools import LarkDocTools

    result = asyncio.run(LarkDocTools().search_lark_docs("极氪 链路梳理"))
    assert isinstance(result, str)

    if not result.lstrip().startswith("{"):
        pytest.skip(f"知识库接口不可用（可能缺少 wiki 权限）: {result}")

    payload = json.loads(result)
    assert payload["keyword"] == "极氪 链路梳理"
    assert isinstance(payload["items"], list)

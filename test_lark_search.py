import os

import pytest
from dotenv import load_dotenv

dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")


@pytest.fixture(autouse=True)
def _load_env():
    load_dotenv(dotenv_path=dotenv_path, override=True)


@pytest.mark.xfail(
    reason=(
        "搜索接口 /open-apis/search/v2/doc_wiki/search 仅接受 user_access_token"
        "（SearchDocWikiRequest.token_types = {USER}），而当前仅配置了应用凭证，"
        "tenant token 会被拒绝（错误码 99991668）。需接入用户授权后才能通过。"
    ),
    strict=False,
)
def test_search_lark_docs():
    """使用客户端调用文档搜索接口（token 由 SDK 自动获取与刷新）"""
    app_id = os.getenv("FEISHU_APP_ID")
    app_secret = os.getenv("FEISHU_APP_SECRET")
    if not app_id or not app_secret:
        pytest.skip("未配置飞书凭证，跳过搜索测试")

    import lark_oapi as lark
    from lark_oapi.api.search.v2 import SearchDocWikiRequest, SearchDocWikiRequestBody

    client = (
        lark.Client.builder()
        .app_id(app_id)
        .app_secret(app_secret)
        .log_level(lark.LogLevel.INFO)
        .build()
    )
    request_body = (
        SearchDocWikiRequestBody.builder().query("极氪 链路梳理").page_size(10).build()
    )
    request = SearchDocWikiRequest.builder().request_body(request_body).build()

    response = client.search.v2.doc_wiki.search(request)

    assert response.success(), f"搜索失败: {response.code}, {response.msg}"
    assert response.data.items is not None

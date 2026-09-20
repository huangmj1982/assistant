import os

import pytest
from dotenv import load_dotenv

dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")


@pytest.fixture(autouse=True)
def _load_env():
    load_dotenv(dotenv_path=dotenv_path, override=True)


def test_feishu_credentials_configured():
    """飞书应用凭证应从 .env 正确加载"""
    if not os.path.exists(dotenv_path):
        pytest.skip("未找到 .env，跳过飞书凭证配置检查")

    assert os.getenv("FEISHU_APP_ID"), "FEISHU_APP_ID 未配置"
    assert os.getenv("FEISHU_APP_SECRET"), "FEISHU_APP_SECRET 未配置"


def test_lark_client_initialization():
    """使用凭证可以初始化飞书客户端"""
    app_id = os.getenv("FEISHU_APP_ID")
    app_secret = os.getenv("FEISHU_APP_SECRET")
    if not app_id or not app_secret:
        pytest.skip("未配置飞书凭证，跳过客户端初始化测试")

    import lark_oapi as lark

    client = (
        lark.Client.builder()
        .app_id(app_id)
        .app_secret(app_secret)
        .log_level(lark.LogLevel.INFO)
        .build()
    )
    assert client is not None

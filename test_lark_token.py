import os

import pytest
import requests
from dotenv import load_dotenv

dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
TOKEN_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"


@pytest.fixture(autouse=True)
def _load_env():
    load_dotenv(dotenv_path=dotenv_path, override=True)


def _require_credentials():
    app_id = os.getenv("FEISHU_APP_ID")
    app_secret = os.getenv("FEISHU_APP_SECRET")
    if not app_id or not app_secret:
        pytest.skip("未配置飞书凭证，跳过在线接口测试")
    return app_id, app_secret


def test_get_tenant_access_token():
    """通过飞书开放接口获取 tenant access token"""
    app_id, app_secret = _require_credentials()

    response = requests.post(
        TOKEN_URL,
        json={"app_id": app_id, "app_secret": app_secret},
        timeout=10,
    )
    assert response.status_code == 200

    result = response.json()
    assert result.get("code") == 0, f"获取 token 失败: {result.get('msg')}"
    assert result.get("tenant_access_token")
    assert result.get("expire", 0) > 0

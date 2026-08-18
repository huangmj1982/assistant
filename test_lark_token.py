import os
import sys
import requests
from dotenv import load_dotenv

# 加载环境变量
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path=dotenv_path)

app_id = os.getenv("FEISHU_APP_ID")
app_secret = os.getenv("FEISHU_APP_SECRET")

print("=" * 70)
print("测试获取飞书tenant access token")
print("=" * 70)

print(f"App ID: {app_id}")
print(f"App Secret: {'*' * len(app_secret) if app_secret else '未设置'}")

if not app_id or not app_secret:
    print("\n❌ 错误：飞书应用凭证未配置！")
    sys.exit(1)

# 调用飞书API获取token
url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
payload = {
    "app_id": app_id,
    "app_secret": app_secret
}

response = requests.post(url, json=payload)
print(f"\n响应状态码: {response.status_code}")
result = response.json()

print("响应内容:")
print(result)

if result.get("code") == 0:
    token = result.get("tenant_access_token")
    expire = result.get("expire")
    print(f"\n✅ 获取token成功: {token[:20]}...")
    print(f"⏰ 过期时间: {expire}秒")
    
    # 测试搜索API
    print("\n🔍 测试搜索API...")
    search_url = "https://open.feishu.cn/open-apis/search/v2/doc_wiki/search"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    search_payload = {
        "query": "极氪 链路梳理",
        "page_size": 10
    }
    
    search_response = requests.post(search_url, headers=headers, json=search_payload)
    print(f"搜索响应状态码: {search_response.status_code}")
    search_result = search_response.json()
    print("搜索响应内容:")
    print(search_result)
    
else:
    print(f"\n❌ 获取token失败: {result.get('msg')}")
    print(f"错误代码: {result.get('code')}")

print("\n" + "=" * 70)

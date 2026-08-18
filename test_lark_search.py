import os
import sys
from dotenv import load_dotenv

# 添加用户 site-packages 到搜索路径
user_site = os.path.expanduser('~/Library/Python/3.12/lib/python/site-packages')
if os.path.exists(user_site):
    sys.path.insert(0, user_site)

# 加载环境变量
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path=dotenv_path)

print("=" * 70)
print("测试飞书文档搜索功能")
print("=" * 70)

app_id = os.getenv("FEISHU_APP_ID")
app_secret = os.getenv("FEISHU_APP_SECRET")

print(f"App ID: {app_id}")
print(f"App Secret: {'*' * len(app_secret) if app_secret else '未设置'}")

if not app_id or not app_secret:
    print("\n❌ 错误：飞书应用凭证未配置！")
    sys.exit(1)

try:
    import lark_oapi as lark
    from lark_oapi.api.auth.v3 import TenantAccessTokenRequest, TenantAccessTokenRequestBody
    from lark_oapi.api.search.v2 import SearchDocWikiRequest, SearchDocWikiRequestBody
    
    # 第一步：获取tenant access token
    print("\n🔑 第一步：获取 tenant access token...")
    
    client = lark.Client.builder() \
        .app_id(app_id) \
        .app_secret(app_secret) \
        .log_level(lark.LogLevel.INFO) \
        .build()
    
    request_body = TenantAccessTokenRequestBody.builder() \
        .app_id(app_id) \
        .app_secret(app_secret) \
        .build()
    
    request = TenantAccessTokenRequest.builder() \
        .request_body(request_body) \
        .build()
    
    response = client.auth.v3.tenant_access_token(request)
    
    if not response.success():
        print(f"❌ 获取token失败: {response.code}, {response.msg}")
        print(f"原始响应: {response.raw.content.decode('utf-8')}")
        sys.exit(1)
    
    token = response.data.tenant_access_token
    print(f"✅ 获取token成功: {token[:20]}...")
    print(f"⏰ 过期时间: {response.data.expire}秒")
    
    # 第二步：使用token搜索文档
    print("\n🔍 第二步：搜索文档...")
    
    # 使用token创建新的客户端
    client = lark.Client.builder() \
        .app_id(app_id) \
        .app_secret(app_secret) \
        .tenant_access_token(token) \
        .log_level(lark.LogLevel.DEBUG) \
        .build()
    
    keyword = "极氪 链路梳理"
    print(f"搜索关键词: {keyword}")
    
    # 创建请求体
    request_body = SearchDocWikiRequestBody.builder() \
        .query(keyword) \
        .page_size(10) \
        .build()
    
    # 创建搜索请求
    request = SearchDocWikiRequest.builder() \
        .request_body(request_body) \
        .build()
    
    # 调用API
    response = client.search.v2.doc_wiki.search(request)
    
    print("\n" + "=" * 70)
    print("API 响应结果:")
    print("=" * 70)
    
    if response.success():
        print("✅ 搜索成功！")
        print(f"找到 {len(response.data.items)} 条结果")
        for i, item in enumerate(response.data.items[:3]):  # 只显示前3条
            print(f"\n{i+1}. {item.title}")
            print(f"   类型: {item.obj_type}")
            print(f"   链接: {item.url}")
    else:
        print("❌ 搜索失败！")
        print(f"错误代码: {response.code}")
        print(f"错误信息: {response.msg}")
        print(f"请求ID: {response.get_log_id()}")
        print(f"原始响应: {response.raw.content.decode('utf-8')}")
        
except Exception as e:
    print(f"\n❌ 发生异常: {str(e)}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)

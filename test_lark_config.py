import os
import sys
from dotenv import load_dotenv

# 添加用户 site-packages 到搜索路径
user_site = os.path.expanduser('~/Library/Python/3.12/lib/python/site-packages')
if os.path.exists(user_site):
    sys.path.insert(0, user_site)

print("=" * 50)
print("测试飞书配置")
print("=" * 50)

# 先测试assistant目录下的.env
print("\n1. 测试 assistant 目录下的 .env 文件")
print("-" * 50)
dotenv_path_assistant = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path=dotenv_path_assistant, override=True)
print(f"加载环境变量文件: {dotenv_path_assistant}")

app_id = os.getenv("FEISHU_APP_ID")
app_secret = os.getenv("FEISHU_APP_SECRET")

print(f"FEISHU_APP_ID: {app_id if app_id else '未设置'}")
print(f"FEISHU_APP_SECRET: {'***' if app_secret else '未设置'}")

if not app_id or not app_secret:
    print("\n错误：飞书应用凭证未配置！")
else:
    print("\n✅ assistant 目录下的 .env 文件配置成功！")

print("\n" + "=" * 50)

# 再测试项目根目录下的.env
print("\n2. 测试项目根目录下的 .env 文件")
print("-" * 50)
dotenv_path_root = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(dotenv_path=dotenv_path_root, override=True)
print(f"加载环境变量文件: {dotenv_path_root}")

app_id = os.getenv("FEISHU_APP_ID")
app_secret = os.getenv("FEISHU_APP_SECRET")

print(f"FEISHU_APP_ID: {app_id if app_id else '未设置'}")
print(f"FEISHU_APP_SECRET: {'***' if app_secret else '未设置'}")

if not app_id or not app_secret:
    print("\n错误：飞书应用凭证未配置！")
    sys.exit(1)

print("\n✅ 项目根目录下的 .env 文件配置成功！")

print("\n" + "=" * 50)

# 尝试初始化飞书客户端
try:
    print("\n尝试初始化飞书客户端...")
    import lark_oapi as lark
    
    client = lark.Client.builder() \
        .app_id(app_id) \
        .app_secret(app_secret) \
        .log_level(lark.LogLevel.INFO) \
        .build()
    
    print("✅ 飞书客户端初始化成功！")
    print("=" * 50)
    
except Exception as e:
    print(f"\n❌ 初始化失败: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 50)
print("测试完成！")
print("=" * 50)

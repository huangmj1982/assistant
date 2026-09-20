import os
import sys
import json
from typing import Optional
from dotenv import load_dotenv
from google.adk.tools.function_tool import FunctionTool

# 添加用户 site-packages 到搜索路径
user_site = os.path.expanduser('~/Library/Python/3.12/lib/python/site-packages')
if os.path.exists(user_site):
    sys.path.insert(0, user_site)

dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(dotenv_path=dotenv_path)

class LarkDocTools:
    def __init__(self):
        self.app_id = os.getenv("FEISHU_APP_ID")
        self.app_secret = os.getenv("FEISHU_APP_SECRET")
        self.client = None
        self.tenant_access_token = None
    
    def get_tenant_access_token(self):
        """手动获取tenant access token"""
        if not self.app_id or not self.app_secret:
            return None
        
        try:
            import lark_oapi as lark
            from lark_oapi.api.auth.v3 import TenantAccessTokenRequest, TenantAccessTokenRequestBody
            
            # 创建临时客户端获取token
            client = lark.Client.builder() \
                .app_id(self.app_id) \
                .app_secret(self.app_secret) \
                .log_level(lark.LogLevel.INFO) \
                .build()
            
            request_body = TenantAccessTokenRequestBody.builder() \
                .app_id(self.app_id) \
                .app_secret(self.app_secret) \
                .build()
            
            request = TenantAccessTokenRequest.builder() \
                .request_body(request_body) \
                .build()
            
            response = client.auth.v3.tenant_access_token(request)
            if response.success():
                self.tenant_access_token = response.data.tenant_access_token
                print("获取 tenant access token 成功")
                return self.tenant_access_token
            else:
                print(f"获取tenant access token失败: {response.code}, {response.msg}")
                return None
                
        except Exception as e:
            print(f"获取tenant access token异常: {str(e)}")
            return None
    
    def get_client(self):
        if not self.client and self.app_id and self.app_secret:
            # 延迟导入，避免启动时卡住
            import lark_oapi as lark
            
            # 先获取token
            token = self.get_tenant_access_token()
            if not token:
                return None
            
            # 使用token创建客户端
            self.client = lark.Client.builder() \
                .app_id(self.app_id) \
                .app_secret(self.app_secret) \
                .tenant_access_token(token) \
                .log_level(lark.LogLevel.INFO) \
                .build()
        return self.client

    async def search_lark_docs(self, keyword: str) -> str:
        """
        搜索飞书文档
        
        Args:
            keyword: 搜索关键词
            
        Returns:
            搜索结果的JSON字符串
        """
        client = self.get_client()
        if not client:
            return "错误：未配置飞书应用凭证（FEISHU_APP_ID 和 FEISHU_APP_SECRET）"
        
        try:
            print(f"搜索飞书文档，关键词: {keyword}")
            
            # 延迟导入，避免启动时卡住
            import lark_oapi as lark
            from lark_oapi.api.search.v2 import SearchDocWikiRequest, SearchDocWikiResponse, SearchDocWikiRequestBody
            
            # 创建请求体
            request_body = SearchDocWikiRequestBody.builder() \
                .query(keyword) \
                .page_size(20) \
                .build()
            
            # 创建搜索请求
            request: SearchDocWikiRequest = SearchDocWikiRequest.builder() \
                .request_body(request_body) \
                .build()
            
            # 调用搜索API
            response: SearchDocWikiResponse = client.search.v2.doc_wiki.search(request)
            
            if not response.success():
                error_msg = f"搜索飞书文档失败, 错误代码: {response.code}, 错误信息: {response.msg}, 请求ID: {response.get_log_id()}"
                print(error_msg)
                # 返回完整错误信息方便排查
                return f"搜索失败: {response.msg} (错误代码: {response.code}, 请求ID: {response.get_log_id()})"
            
            print(f"搜索成功，找到 {len(response.data.items)} 条结果")
            return lark.JSON.marshal(response.data, indent=4)
            
        except Exception as e:
            return f"搜索出错: {str(e)}"

    async def get_lark_doc_content(self, document_id: str) -> str:
        """
        获取飞书文档内容
        
        Args:
            document_id: 飞书文档ID
            
        Returns:
            文档内容的JSON字符串
        """
        client = self.get_client()
        if not client:
            return "错误：未配置飞书应用凭证（FEISHU_APP_ID 和 FEISHU_APP_SECRET）"
        
        try:
            print(f"获取飞书文档内容，文档ID: {document_id}")
            
            # 延迟导入，避免启动时卡住
            import lark_oapi as lark
            from lark_oapi.api.docx.v1 import RawContentDocumentRequest, RawContentDocumentResponse
            
            request: RawContentDocumentRequest = RawContentDocumentRequest.builder() \
                .document_id(document_id) \
                .lang(0) \
                .build()
            
            response: RawContentDocumentResponse = client.docx.v1.document.raw_content(request)
            
            if not response.success():
                print(f"获取文档内容失败, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}")
                return f"获取文档内容失败: {response.msg}"
            
            return lark.JSON.marshal(response.data, indent=4)
            
        except Exception as e:
            return f"获取文档内容出错: {str(e)}"


lark_tools = LarkDocTools()

search_lark_docs_tool = FunctionTool(lark_tools.search_lark_docs)
get_lark_doc_content_tool = FunctionTool(lark_tools.get_lark_doc_content)

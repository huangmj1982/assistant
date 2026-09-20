import logging
import os

from dotenv import load_dotenv
from google.adk.tools.function_tool import FunctionTool

logger = logging.getLogger(__name__)

dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(dotenv_path=dotenv_path)


class LarkDocTools:
    def __init__(self):
        self.app_id = os.getenv("FEISHU_APP_ID")
        self.app_secret = os.getenv("FEISHU_APP_SECRET")
        self.client = None

    def get_client(self):
        """获取飞书客户端。

        lark SDK 内部（TokenManager）会自动获取并缓存 tenant access token，
        并在过期前自动刷新，因此这里只需用 app_id/app_secret 构建客户端，
        无需手动获取与维护 token。
        """
        if not self.app_id or not self.app_secret:
            return None

        if self.client is None:
            # 延迟导入，避免启动时卡住
            import lark_oapi as lark

            self.client = lark.Client.builder() \
                .app_id(self.app_id) \
                .app_secret(self.app_secret) \
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
            logger.info("搜索飞书文档，关键词: %s", keyword)

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
                logger.error(
                    "搜索飞书文档失败, 错误代码: %s, 错误信息: %s, 请求ID: %s",
                    response.code,
                    response.msg,
                    response.get_log_id(),
                )
                # 返回完整错误信息方便排查
                return f"搜索失败: {response.msg} (错误代码: {response.code}, 请求ID: {response.get_log_id()})"

            logger.info("搜索成功，找到 %s 条结果", len(response.data.items))
            return lark.JSON.marshal(response.data, indent=4)

        except Exception as e:
            logger.exception("搜索飞书文档异常: %s", e)
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
            logger.info("获取飞书文档内容，文档ID: %s", document_id)

            # 延迟导入，避免启动时卡住
            import lark_oapi as lark
            from lark_oapi.api.docx.v1 import RawContentDocumentRequest, RawContentDocumentResponse

            request: RawContentDocumentRequest = RawContentDocumentRequest.builder() \
                .document_id(document_id) \
                .lang(0) \
                .build()

            response: RawContentDocumentResponse = client.docx.v1.document.raw_content(request)

            if not response.success():
                logger.error(
                    "获取文档内容失败, code: %s, msg: %s, log_id: %s",
                    response.code,
                    response.msg,
                    response.get_log_id(),
                )
                return f"获取文档内容失败: {response.msg}"

            return lark.JSON.marshal(response.data, indent=4)

        except Exception as e:
            logger.exception("获取文档内容异常: %s", e)
            return f"获取文档内容出错: {str(e)}"


lark_tools = LarkDocTools()

search_lark_docs_tool = FunctionTool(lark_tools.search_lark_docs)
get_lark_doc_content_tool = FunctionTool(lark_tools.get_lark_doc_content)

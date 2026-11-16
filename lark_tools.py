import asyncio
import logging
import os
import re
from urllib.parse import urlparse

from dotenv import load_dotenv
from google.adk.tools.function_tool import FunctionTool

dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(dotenv_path=dotenv_path)

logger = logging.getLogger(__name__)


class LarkDocTools:
    """飞书文档工具：搜索文档与读取文档内容。

    客户端仅使用 app_id/app_secret 构建，lark-oapi SDK 内置 TokenManager
    会自动获取并续期 tenant_access_token，无需手动管理。
    """

    def __init__(self):
        self.app_id = os.getenv("FEISHU_APP_ID")
        self.app_secret = os.getenv("FEISHU_APP_SECRET")
        self._client = None

    def _get_client(self):
        """延迟构建飞书客户端；凭证缺失或构建失败时返回 None。"""
        if self._client is not None:
            return self._client
        if not self.app_id or not self.app_secret:
            return None
        try:
            import lark_oapi as lark

            self._client = (
                lark.Client.builder()
                .app_id(self.app_id)
                .app_secret(self.app_secret)
                .log_level(lark.LogLevel.WARNING)
                .build()
            )
        except Exception as e:
            logger.error("初始化飞书客户端失败: %s", self._redact_sensitive(e))
            return None
        return self._client

    def _missing_credentials_msg(self) -> str:
        return "错误：未配置飞书应用凭证（FEISHU_APP_ID 和 FEISHU_APP_SECRET）"

    def _redact_sensitive(self, value) -> str:
        text = str(value)
        if self.app_secret:
            text = text.replace(self.app_secret, "[REDACTED]")
        return re.sub(r"\b[tu]-[A-Za-z0-9_-]+\b", "[REDACTED]", text)

    @staticmethod
    def _extract_document_id(document_id: str) -> str:
        if not isinstance(document_id, str) or not document_id.strip():
            raise ValueError("文档ID或链接不能为空")

        value = document_id.strip()
        parsed = urlparse(value)
        if parsed.scheme or parsed.netloc:
            parts = [part for part in parsed.path.split("/") if part]
            if len(parts) == 2 and parts[0] in {"docx", "wiki"}:
                return parts[1]
            raise ValueError("无效的飞书文档链接")
        return value

    async def search_lark_docs(self, keyword: str) -> str:
        """
        搜索飞书文档

        Args:
            keyword: 搜索关键词

        Returns:
            搜索结果的JSON字符串
        """
        client = self._get_client()
        if not client:
            return self._missing_credentials_msg()

        def _do_search() -> str:
            import lark_oapi as lark
            from lark_oapi.api.search.v2 import (
                SearchDocWikiRequest,
                SearchDocWikiRequestBody,
            )

            request_body = (
                SearchDocWikiRequestBody.builder()
                .query(keyword)
                .page_size(20)
                .build()
            )
            request = (
                SearchDocWikiRequest.builder()
                .request_body(request_body)
                .build()
            )

            response = client.search.v2.doc_wiki.search(request)

            if not response.success():
                safe_msg = self._redact_sensitive(response.msg)
                logger.warning(
                    "搜索飞书文档失败, code: %s, msg: %s, log_id: %s",
                    response.code,
                    safe_msg,
                    response.get_log_id(),
                )
                return f"搜索失败: {safe_msg} (错误代码: {response.code}, 请求ID: {response.get_log_id()})"

            logger.info("搜索飞书文档成功，关键词: %s", keyword)
            return lark.JSON.marshal(response.data, indent=4)

        try:
            return await asyncio.to_thread(_do_search)
        except Exception as e:
            safe_msg = self._redact_sensitive(e)
            logger.error("搜索飞书文档异常: %s", safe_msg)
            return f"搜索出错: {safe_msg}"

    async def get_lark_doc_content(self, document_id: str) -> str:
        """
        获取飞书文档内容

        Args:
            document_id: 飞书文档ID

        Returns:
            文档内容的JSON字符串
        """
        try:
            document_id = self._extract_document_id(document_id)
        except ValueError as e:
            return f"获取文档内容出错: {e}"

        client = self._get_client()
        if not client:
            return self._missing_credentials_msg()

        def _do_get_content() -> str:
            import lark_oapi as lark
            from lark_oapi.api.docx.v1 import RawContentDocumentRequest

            request = (
                RawContentDocumentRequest.builder()
                .document_id(document_id)
                .lang(0)
                .build()
            )

            response = client.docx.v1.document.raw_content(request)

            if not response.success():
                safe_msg = self._redact_sensitive(response.msg)
                logger.warning(
                    "获取文档内容失败, code: %s, msg: %s, log_id: %s",
                    response.code,
                    safe_msg,
                    response.get_log_id(),
                )
                return f"获取文档内容失败: {safe_msg}"

            return lark.JSON.marshal(response.data, indent=4)

        try:
            return await asyncio.to_thread(_do_get_content)
        except Exception as e:
            safe_msg = self._redact_sensitive(e)
            logger.error("获取飞书文档内容异常: %s", safe_msg)
            return f"获取文档内容出错: {safe_msg}"


lark_tools = LarkDocTools()

search_lark_docs_tool = FunctionTool(lark_tools.search_lark_docs)
get_lark_doc_content_tool = FunctionTool(lark_tools.get_lark_doc_content)

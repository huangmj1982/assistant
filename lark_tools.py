import json
import logging
import os

from dotenv import load_dotenv
from google.adk.tools.function_tool import FunctionTool

logger = logging.getLogger(__name__)

dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(dotenv_path=dotenv_path)

# 知识库标题匹配的遍历上限，避免知识库规模较大时遍历过多节点
MAX_SPACES = 20
MAX_NODES_PER_SPACE = 200
MAX_RESULTS = 20


class LarkDocTools:
    def __init__(self):
        self.app_id = os.getenv("FEISHU_APP_ID")
        self.app_secret = os.getenv("FEISHU_APP_SECRET")
        # 可选：配置后启用全库全文搜索（该接口仅接受 user_access_token）
        self.user_access_token = os.getenv("FEISHU_USER_ACCESS_TOKEN")
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

    def _search_full_text(self, client, keyword: str):
        """使用 user_access_token 调用全库搜索接口（支持全文检索）。

        接口：/open-apis/search/v2/doc_wiki/search，token_types = {USER}，
        因此必须通过 RequestOption 传入 user_access_token。

        失败时返回 None，由调用方降级处理。
        """
        # 延迟导入，避免启动时卡住
        import lark_oapi as lark
        from lark_oapi.api.search.v2 import SearchDocWikiRequest, SearchDocWikiRequestBody

        request_body = SearchDocWikiRequestBody.builder() \
            .query(keyword) \
            .page_size(20) \
            .build()
        request = SearchDocWikiRequest.builder().request_body(request_body).build()
        option = lark.RequestOption.builder().user_access_token(self.user_access_token).build()

        response = client.search.v2.doc_wiki.search(request, option)
        if not response.success():
            logger.error(
                "全文搜索失败, code: %s, msg: %s, log_id: %s",
                response.code,
                response.msg,
                response.get_log_id(),
            )
            return None

        data = response.data
        units = getattr(data, "res_units", None) or []
        items = [json.loads(lark.JSON.marshal(unit)) for unit in units]
        logger.info("全文搜索成功，命中 %s 条", len(items))
        return lark.JSON.marshal(
            {
                "keyword": keyword,
                "mode": "full_text",
                "total": getattr(data, "total", len(items)),
                "items": items,
            },
            indent=4,
        )

    def _match_nodes_in_space(self, client, space, keyword: str):
        """在单个知识库空间内按标题匹配节点（带分页与上限保护）"""
        from lark_oapi.api.wiki.v2 import ListSpaceNodeRequest

        matched = []
        page_token = None
        fetched = 0
        while fetched < MAX_NODES_PER_SPACE and len(matched) < MAX_RESULTS:
            builder = ListSpaceNodeRequest.builder() \
                .space_id(space.space_id) \
                .page_size(50)
            # 首次请求不能携带空 page_token，否则接口报 131002 invalid page label
            if page_token:
                builder = builder.page_token(page_token)
            request = builder.build()

            response = client.wiki.v2.space_node.list(request)
            if not response.success():
                logger.warning(
                    "列举知识库节点失败(space_id=%s), code: %s, msg: %s",
                    space.space_id,
                    response.code,
                    response.msg,
                )
                break

            items = response.data.items or []
            fetched += len(items)
            for node in items:
                if keyword.lower() in (node.title or "").lower():
                    matched.append({
                        "title": node.title,
                        "node_token": node.node_token,
                        "obj_token": node.obj_token,
                        "obj_type": node.obj_type,
                        "node_type": node.node_type,
                        "space_id": node.space_id,
                        "space_name": space.name,
                    })
                    if len(matched) >= MAX_RESULTS:
                        break

            if not response.data.has_more:
                break
            page_token = response.data.page_token

        return matched

    def _search_wiki_by_title(self, client, keyword: str) -> str:
        """降级方案：列举知识库空间与节点，按标题匹配关键词（tenant token 可用）"""
        # 延迟导入，避免启动时卡住
        import lark_oapi as lark
        from lark_oapi.api.wiki.v2 import ListSpaceRequest

        matched = []
        space_count = 0
        page_token = None
        while True:
            builder = ListSpaceRequest.builder().page_size(50)
            # 首次请求不能携带空 page_token，否则接口报 131002 invalid page label
            if page_token:
                builder = builder.page_token(page_token)
            space_request = builder.build()

            space_response = client.wiki.v2.space.list(space_request)
            if not space_response.success():
                logger.error(
                    "列举知识库空间失败, code: %s, msg: %s, log_id: %s",
                    space_response.code,
                    space_response.msg,
                    space_response.get_log_id(),
                )
                return f"检索失败: {space_response.msg} (错误代码: {space_response.code})"

            for space in space_response.data.items or []:
                if space_count >= MAX_SPACES or len(matched) >= MAX_RESULTS:
                    break
                space_count += 1
                matched.extend(self._match_nodes_in_space(client, space, keyword))

            if (
                not space_response.data.has_more
                or space_count >= MAX_SPACES
                or len(matched) >= MAX_RESULTS
            ):
                break
            page_token = space_response.data.page_token

        logger.info("知识库标题匹配完成，命中 %s 条（已扫描 %s 个空间）", len(matched), space_count)
        return lark.JSON.marshal(
            {
                "keyword": keyword,
                "mode": "wiki_title",
                "total": len(matched),
                "items": matched,
            },
            indent=4,
        )

    async def search_lark_docs(self, keyword: str) -> str:
        """
        搜索飞书文档

        检索策略：
        1. 若配置了 FEISHU_USER_ACCESS_TOKEN，则调用全库全文搜索接口
           （/open-apis/search/v2/doc_wiki/search，仅接受 user_access_token）；
        2. 否则降级为知识库（Wiki）节点标题匹配（tenant token 即可），
           覆盖范围为 Wiki 知识库、精度为标题匹配。

        返回结果中的 obj_token 可直接作为 get_lark_doc_content 的 document_id 读取正文。

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

            if self.user_access_token:
                result = self._search_full_text(client, keyword)
                if result is not None:
                    return result
                logger.warning("全文搜索不可用，降级为知识库标题匹配")

            return self._search_wiki_by_title(client, keyword)

        except Exception as e:
            logger.exception("搜索飞书文档异常: %s", e)
            return f"搜索出错: {str(e)}"

    async def get_lark_doc_content(self, document_id: str) -> str:
        """
        获取飞书文档内容

        Args:
            document_id: 飞书文档ID（可使用 search_lark_docs 返回的 obj_token）

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

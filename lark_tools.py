import logging
import os

from dotenv import load_dotenv
from google.adk.tools.function_tool import FunctionTool

logger = logging.getLogger(__name__)

dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(dotenv_path=dotenv_path)

# 检索上限，避免知识库规模较大时遍历过多节点
MAX_SPACES = 20
MAX_NODES_PER_SPACE = 200
MAX_RESULTS = 20


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

    async def search_lark_docs(self, keyword: str) -> str:
        """
        按关键词检索飞书知识库文档（基于知识库节点标题匹配）

        说明：飞书全库全文搜索接口（/open-apis/search/v2/doc_wiki/search）的
        token_types 为 {USER}，仅接受 user_access_token，应用凭证无法调用。
        因此这里改用知识库（Wiki）空间与节点列举接口（支持 tenant token），
        在本地按标题做关键词匹配，使工具在仅有应用凭证时也可用。
        返回结果中的 obj_token 可直接作为 get_lark_doc_content 的 document_id 读取正文。

        Args:
            keyword: 搜索关键词（匹配文档标题）

        Returns:
            搜索结果的JSON字符串
        """
        client = self.get_client()
        if not client:
            return "错误：未配置飞书应用凭证（FEISHU_APP_ID 和 FEISHU_APP_SECRET）"

        try:
            logger.info("检索飞书知识库文档，关键词: %s", keyword)

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

            logger.info("检索完成，命中 %s 条（已扫描 %s 个知识库空间）", len(matched), space_count)
            return lark.JSON.marshal(
                {"keyword": keyword, "total": len(matched), "items": matched}, indent=4
            )

        except Exception as e:
            logger.exception("检索飞书知识库文档异常: %s", e)
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

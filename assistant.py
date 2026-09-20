# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import logging

from google.adk.agents import RunConfig
from google.adk.agents.run_config import StreamingMode
from google.genai.types import Content, Part
from veadk import Agent, Runner

from agentkit.apps import AgentkitSimpleApp
from veadk.prompts.agent_default_prompt import DEFAULT_DESCRIPTION, DEFAULT_INSTRUCTION

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _error_event(error_type: str, message: str) -> str:
    """构造错误事件，与正常事件的 JSON 结构保持一致，便于客户端统一解析"""
    return json.dumps(
        {"error": {"type": error_type, "message": message}}, ensure_ascii=False
    )


app = AgentkitSimpleApp()

app_name = "simple_streamable_app"

agent_name = "Agent"
description = DEFAULT_DESCRIPTION 
system_prompt = DEFAULT_INSTRUCTION 


tools = []

# from veadk.tools.builtin_tools.web_search import web_search
# tools.append(web_search)


agent = Agent(
    name=agent_name,
    description=description,
    instruction=system_prompt,
    tools=tools,
)
# veADK 通过私有属性透传 stream_options，这里做防御性判断，避免 SDK 升级后属性缺失导致启动失败
_additional_args = getattr(getattr(agent, "model", None), "_additional_args", None)
if _additional_args is not None:
    _additional_args["stream_options"] = {"include_usage": True}
else:
    logger.warning(
        "无法设置 stream_options：agent.model._additional_args 不可用，可能 SDK 版本已变更"
    )
runner = Runner(agent=agent, app_name=app_name)


@app.entrypoint
async def run(payload: dict, headers: dict):
    prompt = payload.get("prompt")
    user_id = headers.get("user_id")
    session_id = headers.get("session_id")

    if not prompt or not user_id or not session_id:
        logger.error(
            "Missing required field(s): prompt=%s, user_id=%s, session_id=%s",
            bool(prompt),
            bool(user_id),
            bool(session_id),
        )
        yield _error_event(
            "MissingParameter", "missing required field(s): prompt/user_id/session_id"
        )
        return

    logger.info(
        f"Running agent with prompt: {prompt}, user_id: {user_id}, session_id: {session_id}"
    )

    session_service = runner.short_term_memory.session_service  # type: ignore

    # prevent session recreation
    session = await session_service.get_session(
        app_name=app_name, user_id=user_id, session_id=session_id
    )
    if not session:
        await session_service.create_session(
            app_name=app_name, user_id=user_id, session_id=session_id
        )

    new_message = Content(role="user", parts=[Part(text=prompt)])
    try:
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=new_message,
            run_config=RunConfig(streaming_mode=StreamingMode.SSE),
        ):
            # Format as SSE data
            sse_event = event.model_dump_json(exclude_none=True, by_alias=True)
            logger.debug("Generated event in agent run streaming: %s", sse_event)
            yield sse_event
    except Exception as e:
        logger.exception("Error in event_generator: %s", e)
        yield _error_event(type(e).__name__, str(e))


@app.ping
def ping() -> str:
    return "pong!"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
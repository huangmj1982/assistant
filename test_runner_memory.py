"""Runner 短期记忆测试：mock Agent 执行，不调用模型或外部服务。"""
import asyncio

from veadk import Runner
from veadk.memory import ShortTermMemory


class _FakeAgent:
    skills = []
    long_term_memory = None
    run_processor = None


def test_runner_reuses_same_session_and_isolates_other_sessions():
    async def exercise():
        memory = ShortTermMemory(backend="local")
        runner = Runner(
            agent=_FakeAgent(),
            app_name="memory-test",
            user_id="user-1",
            short_term_memory=memory,
        )

        async def no_model_events(**kwargs):
            if False:
                yield None

        runner.run_async = no_model_events

        await runner.run(messages="第一条消息", session_id="session-a")
        first = await memory.session_service.get_session(
            app_name="memory-test", user_id="user-1", session_id="session-a"
        )

        await runner.run(messages="第二条消息", session_id="session-a")
        reused = await memory.session_service.get_session(
            app_name="memory-test", user_id="user-1", session_id="session-a"
        )
        # InMemorySessionService 返回深拷贝，用 ID 断言复用而非对象身份
        assert reused.id == first.id

        await runner.run(messages="另一个会话", session_id="session-b")
        isolated = await memory.session_service.get_session(
            app_name="memory-test", user_id="user-1", session_id="session-b"
        )
        assert isolated.id != first.id
        assert isolated.events == []

    asyncio.run(exercise())

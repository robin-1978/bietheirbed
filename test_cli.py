import asyncio
from pc_assistant.agent import Agent
from pc_assistant.config import AppConfig

async def test():
    agent = Agent(config=AppConfig())
    if not await agent.health_check():
        print("Server not available!")
        return

    print("=== Test 1: Simple question (should not call tools) ===")
    async for event in agent.run("今天是几号？你知道吗？"):
        if event.type == "stream_delta":
            print(event.content, end="", flush=True)
        elif event.type == "stream_end":
            print()
        elif event.type == "tool_call":
            print(f"\n[TOOL] {event.tool_name}({event.tool_args}) blocked={event.blocked}")
        elif event.type == "tool_result":
            print(f"\n[RESULT] {str(event.tool_result)[:200]}")
        elif event.type == "final_answer":
            print(f"\n[FINAL] {event.content[:300]}")
        elif event.type == "error":
            print(f"\n[ERROR] {event.content[:200]}")
        elif event.type == "thought":
            print(f"\n[THINKING] {event.content[:200]}")
        elif event.type == "iteration_limit":
            print(f"\n[LIMIT] {event.content}")

    print("\n\n=== Test 2: Web search ===")
    async for event in agent.run("查一下上海天气"):
        if event.type == "stream_delta":
            print(event.content, end="", flush=True)
        elif event.type == "stream_end":
            print()
        elif event.type == "tool_call":
            print(f"\n[TOOL] {event.tool_name}({event.tool_args}) blocked={event.blocked}")
        elif event.type == "tool_result":
            print(f"\n[RESULT] {str(event.tool_result)[:300]}")
        elif event.type == "final_answer":
            print(f"\n[FINAL] {event.content[:500]}")
        elif event.type == "error":
            print(f"\n[ERROR] {event.content[:200]}")
        elif event.type == "thought":
            print(f"\n[THINKING] {event.content[:200]}")
        elif event.type == "iteration_limit":
            print(f"\n[LIMIT] {event.content}")

asyncio.run(test())

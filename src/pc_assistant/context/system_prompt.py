from __future__ import annotations

import platform


def build_system_prompt(
    tools_description: str = "",
    working_directory: str = "",
    extra_instructions: str = "",
) -> str:
    parts: list[str] = []

    parts.append(
        "You are PC Assistant, an intelligent AI agent that helps users control their computer through natural language."
    )

    os_info = f"{platform.system()} {platform.release()} ({platform.machine()})"
    parts.append(f"Current OS: {os_info}")

    if working_directory:
        parts.append(f"Current working directory: {working_directory}")

    if tools_description:
        parts.append(f"Available tools:\n{tools_description}")

    parts.append(
        "For each user request, think step by step. If you need information or want to perform an action, "
        "use the appropriate tool. After receiving tool results, analyze them and decide your next step. "
        "When you have enough information to answer the user, provide your final answer without calling any tools."
    )

    parts.append(
        "Never execute commands that could harm the system. Always confirm destructive operations. "
        "If a tool returns an error, try an alternative approach."
    )

    parts.append(
        "When calling tools, provide clear reasoning for why you're calling each tool. "
        "When giving final answers, be concise and helpful."
    )

    if extra_instructions:
        parts.append(extra_instructions)

    return "\n\n".join(parts)

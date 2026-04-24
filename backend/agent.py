import json
import os
from typing import Any, TypedDict

from backend.crm_tools import build_tool_registry, normalize_payload

try:
    from langchain_openai import ChatOpenAI
except ImportError:  # pragma: no cover
    ChatOpenAI = None

from langgraph.graph import END, START, StateGraph


TOOLS = build_tool_registry()


class AgentState(TypedDict, total=False):
    messages: list[dict[str, str]]
    action: str
    user_input: str
    form_data: dict[str, Any]
    current_state: dict[str, Any]
    matched_entry_id: int | None
    next_tool: str | None
    tool_input: dict[str, Any]
    last_tool_name: str | None
    last_observation: dict[str, Any]
    response: dict[str, Any]


def _tool_step(tool_name: str, tool_input: dict[str, Any], note: str) -> dict[str, Any]:
    return {
        "next_tool": tool_name,
        "tool_input": tool_input,
        "messages": [{"role": "assistant", "content": note}],
    }


def _response_step(payload: dict[str, Any]) -> dict[str, Any]:
    return {"response": payload, "next_tool": None, "tool_input": {}}


def llm_plan_message_tool(state: AgentState) -> dict[str, Any] | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or ChatOpenAI is None or state.get("action") != "process_message":
        return None

    model = ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"), api_key=api_key, temperature=0)
    current_state = normalize_payload(state.get("current_state", {}) or {})
    try:
        response = model.invoke(
            [
                {
                    "role": "system",
                    "content": (
                        "Choose exactly one tool for this CRM request. Return only JSON with keys "
                        "'tool_name', 'tool_input', and 'reason'. Allowed tools: LogInteractionTool, EditInteractionTool."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "user_input": state.get("user_input", ""),
                            "current_state": current_state,
                        }
                    ),
                },
            ]
        )
        content = getattr(response, "content", "") or "{}"
        parsed = json.loads(content if content.strip().startswith("{") else "{}")
        tool_name = parsed.get("tool_name")
        if tool_name not in {"LogInteractionTool", "EditInteractionTool"}:
            return None
        tool_input = parsed.get("tool_input", {})
        if tool_name == "LogInteractionTool":
            tool_input = {"operation": "extract", "text": state.get("user_input", ""), **tool_input}
        else:
            tool_input = {
                "instruction": state.get("user_input", ""),
                "current_state": current_state,
                **tool_input,
            }
        return _tool_step(tool_name, tool_input, str(parsed.get("reason", "Planning next tool.")))
    except Exception:
        return None


def llm_node(state: AgentState) -> dict[str, Any]:
    if state.get("response"):
        return {}

    llm_plan = llm_plan_message_tool(state)
    if llm_plan:
        return llm_plan

    action = state.get("action")
    last_tool_name = state.get("last_tool_name")
    last_observation = state.get("last_observation", {})

    if action == "list_entries":
        if not last_tool_name:
            return _tool_step("LogInteractionTool", {"operation": "list"}, "Loading saved interactions.")
        return _response_step(
            {
                "status": "listed",
                "entries": last_observation.get("entries", []),
                "message": "Saved interactions loaded.",
            }
        )

    if action == "process_message":
        current_state = normalize_payload(state.get("current_state", {}) or {})
        if not last_tool_name:
            if any(current_state.values()):
                return _tool_step(
                    "EditInteractionTool",
                    {
                        "instruction": state.get("user_input", ""),
                        "current_state": current_state,
                    },
                    "Updating the current interaction form.",
                )
            return _tool_step(
                "LogInteractionTool",
                {
                    "operation": "extract",
                    "text": state.get("user_input", ""),
                },
                "Extracting a new interaction draft.",
            )

        form_data = normalize_payload(last_observation.get("form_data", {}) or {})
        return _response_step(
            {
                "status": "form_updated",
                "form_data": form_data,
                "message": "Form updated from your message.",
            }
        )

    if action == "save_entry":
        if not last_tool_name:
            return _tool_step(
                "DuplicateCheckTool",
                {"entry": state.get("form_data", {}) or {}},
                "Checking saved interactions for duplicates.",
            )
        if last_tool_name == "DuplicateCheckTool":
            if last_observation.get("is_duplicate"):
                return _response_step(
                    {
                        "status": "duplicate_detected",
                        "duplicate": last_observation,
                        "message": "Duplicate interaction detected. Do you want to merge or save as new?",
                    }
                )
            return _tool_step(
                "FollowUpSuggestionTool",
                {"entry": state.get("form_data", {}) or {}},
                "Generating follow-up suggestions before saving.",
            )
        if last_tool_name == "FollowUpSuggestionTool":
            entry = {**normalize_payload(state.get("form_data", {}) or {}), **last_observation}
            return _tool_step(
                "LogInteractionTool",
                {"operation": "save", "entry": entry},
                "Saving the interaction to the database.",
            )
        return _response_step(
            {
                "status": "saved",
                "entry": last_observation.get("entry", {}),
                "entries": last_observation.get("entries", []),
                "message": "Interaction saved successfully.",
            }
        )

    if action == "save_new_entry":
        if not last_tool_name:
            return _tool_step(
                "FollowUpSuggestionTool",
                {"entry": state.get("form_data", {}) or {}},
                "Preparing follow-up suggestions for the new interaction.",
            )
        if last_tool_name == "FollowUpSuggestionTool":
            entry = {**normalize_payload(state.get("form_data", {}) or {}), **last_observation}
            return _tool_step(
                "LogInteractionTool",
                {"operation": "save", "entry": entry},
                "Saving the interaction as a new record.",
            )
        return _response_step(
            {
                "status": "saved",
                "entry": last_observation.get("entry", {}),
                "entries": last_observation.get("entries", []),
                "message": "Interaction saved as a new record.",
            }
        )

    if action == "merge_entry":
        if not last_tool_name:
            return _tool_step(
                "MergeInteractionTool",
                {
                    "existing_id": state.get("matched_entry_id"),
                    "new_entry": state.get("form_data", {}) or {},
                },
                "Merging the duplicate interaction into the saved record.",
            )
        return _response_step(
            {
                "status": "merged",
                "entry": last_observation.get("entry", {}),
                "entries": last_observation.get("entries", []),
                "message": "Duplicate interaction merged successfully.",
            }
        )

    return _response_step({"status": "error", "message": "Unknown agent action."})


def tool_node(state: AgentState) -> dict[str, Any]:
    tool_name = state.get("next_tool")
    if not tool_name:
        return {}
    tool = TOOLS[tool_name]
    observation = tool.run(state.get("tool_input", {}) or {})
    return {
        "last_tool_name": tool_name,
        "last_observation": observation,
        "next_tool": None,
        "tool_input": {},
        "messages": [{"role": "tool", "content": json.dumps(observation)}],
    }


def route_after_llm(state: AgentState) -> str:
    return "tool_node" if state.get("next_tool") else END


graph = StateGraph(AgentState)
graph.add_node("llm_node", llm_node)
graph.add_node("tool_node", tool_node)
graph.add_edge(START, "llm_node")
graph.add_conditional_edges("llm_node", route_after_llm, {"tool_node": "tool_node", END: END})
graph.add_edge("tool_node", "llm_node")
agent_graph = graph.compile()


def invoke_agent(payload: dict[str, Any]) -> dict[str, Any]:
    initial_state: AgentState = {
        "messages": [{"role": "user", "content": json.dumps(payload)}],
        "action": payload.get("action", ""),
        "user_input": payload.get("user_input", "") or "",
        "form_data": payload.get("form_data", {}) or {},
        "current_state": payload.get("current_state", {}) or {},
        "matched_entry_id": payload.get("matched_entry_id"),
        "response": {},
    }
    result = agent_graph.invoke(initial_state)
    return result.get("response", {"status": "error", "message": "Agent did not return a response."})

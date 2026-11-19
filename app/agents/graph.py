from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from app.agents.nodes import assistant_node
from app.agents.state import RefundAgentState
from app.services.refund_service import RefundService
from app.services.policy_rag_service import PolicyRagService
from app.tools.refund_tools import build_refund_tools


def build_graph(
    model: BaseChatModel,
    service: RefundService,
    user_name: str,
    policy_service: PolicyRagService | None = None,
):
    tools = build_refund_tools(service, policy_service)
    workflow = StateGraph(RefundAgentState)

    # The assistant chooses whether to answer or call a tool.
    workflow.add_node(
        "assistant",
        assistant_node(
            model.bind_tools(tools),
            user_name,
            policy_search_enabled=policy_service is not None,
        ),
    )

    # ToolNode executes the selected LangChain tool and returns its result to the assistant.
    workflow.add_node("tools", ToolNode(tools))

    workflow.add_edge(START, "assistant")
    workflow.add_conditional_edges("assistant", tools_condition, {"tools": "tools", END: END})
    workflow.add_edge("tools", "assistant")

    return workflow.compile(checkpointer=MemorySaver())

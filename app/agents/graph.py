from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from app.agents.nodes import assistant_node
from app.agents.state import RefundAgentState
from app.services.refund_service import RefundService
from app.tools.refund_tools import build_refund_tools


def build_graph(model: BaseChatModel, service: RefundService, checkpointer=None):
    tools = build_refund_tools(service)
    workflow = StateGraph(RefundAgentState)
    workflow.add_node("assistant", assistant_node(model.bind_tools(tools)))
    workflow.add_node("tools", ToolNode(tools))
    workflow.add_edge(START, "assistant")
    workflow.add_conditional_edges("assistant", tools_condition, {"tools": "tools", END: END})
    workflow.add_edge("tools", "assistant")
    return workflow.compile(checkpointer=checkpointer or MemorySaver())

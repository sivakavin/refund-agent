from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage
from app.agents.prompts import SYSTEM_PROMPT


def assistant_node(model: BaseChatModel):
    def run(state: dict):
        messages = state["messages"]
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=SYSTEM_PROMPT), *messages]
        return {"messages": [model.invoke(messages)]}
    return run

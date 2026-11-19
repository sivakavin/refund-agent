from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage
from app.agents.prompts import system_prompt


def assistant_node(model: BaseChatModel, user_name: str, policy_search_enabled: bool = False):
    prompt = system_prompt(user_name, policy_search_enabled)

    def run(state: dict):
        messages = state["messages"]
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=prompt), *messages]
        return {"messages": [model.invoke(messages)]}

    return run

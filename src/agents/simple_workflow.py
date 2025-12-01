from typing import TypedDict
from langgraph.graph import StateGraph, START, END


class State(TypedDict):
    message: str
    count: int


def node_1(state: State) -> State:
    return {"message": state["message"] + " -> Node 1", "count": state["count"] + 1}


def node_2(state: State) -> State:
    return {"message": state["message"] + " -> Node 2", "count": state["count"] + 1}


def create_workflow():
    workflow = StateGraph(State)

    workflow.add_node("node_1", node_1)
    workflow.add_node("node_2", node_2)

    workflow.add_edge(START, "node_1")
    workflow.add_edge("node_1", "node_2")
    workflow.add_edge("node_2", END)

    return workflow.compile()


# For testing
if __name__ == "__main__":
    graph = create_workflow()
    result = graph.invoke({"message": "Start", "count": 0})
    print(result)

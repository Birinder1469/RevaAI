from typing import TypedDict, List
from langgraph.graph import StateGraph, START, END


class PricingState(TypedDict):
    product_catalog: List[dict]
    competitor_data: List[dict]
    matched_skus: List[dict]
    normalized_promos: List[dict]
    recommendation: dict


def matcher_node(state: PricingState) -> PricingState:
    """Match SKUs to competitor products"""
    # TODO: Your matcher logic
    matched = [{"sku": "TV-123", "competitor_sku": "COMP-456", "confidence": 0.95}]
    return {**state, "matched_skus": matched}


def promo_normalizer_node(state: PricingState) -> PricingState:
    """Normalize promotional text"""
    # TODO: Your promo normalizer logic
    normalized = [{"promo": "Save $300", "normalized_value": 300, "type": "dollar_off"}]
    return {**state, "normalized_promos": normalized}


def simulator_node(state: PricingState) -> PricingState:
    """Simulate pricing scenarios"""
    # TODO: Your simulator logic
    recommendation = {"optimal_price": 799.99, "expected_margin": 0.25}
    return {**state, "recommendation": recommendation}


def create_workflow():
    workflow = StateGraph(PricingState)

    # Add nodes
    workflow.add_node("matcher", matcher_node)
    workflow.add_node("promo_normalizer", promo_normalizer_node)
    workflow.add_node("simulator", simulator_node)

    # Define flow
    workflow.add_edge(START, "matcher")
    workflow.add_edge("matcher", "promo_normalizer")
    workflow.add_edge("promo_normalizer", "simulator")
    workflow.add_edge("simulator", END)

    return workflow.compile()

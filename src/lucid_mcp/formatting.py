"""Formatting utilities for Lucid MCP."""

from typing import Any

from graphiti_core.edges import EntityEdge
from graphiti_core.nodes import EntityNode


def format_node_result(node: EntityNode) -> dict[str, Any]:
    """Format an entity node result and strip embeddings."""
    result = node.model_dump(
        mode='json',
        exclude={
            'name_embedding',
        },
    )
    result.get('attributes', {}).pop('name_embedding', None)
    return result


def format_fact_result(edge: EntityEdge) -> dict[str, Any]:
    """Format an entity edge result and strip embeddings."""
    result = edge.model_dump(
        mode='json',
        exclude={
            'fact_embedding',
        },
    )
    result.get('attributes', {}).pop('fact_embedding', None)
    return result

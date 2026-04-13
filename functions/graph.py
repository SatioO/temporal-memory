from dataclasses import dataclass
from typing import List, Optional
from logger import get_logger
from datetime import datetime, timezone
from iii import IIIClient
from state.kv import StateKV
from state.schema import KV, generate_id
from schema.base import Model

logger = get_logger("graph")


@dataclass(frozen=True)
class GraphNode(Model):
    id: str
    label: str
    type: str
    properties: dict
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class GraphEdge(Model):
    id: str
    source_id: str
    target_id: str
    relation: str
    weight: float
    created_at: str


@dataclass(frozen=True)
class AddNodePayload(Model):
    label: str
    type: str
    properties: Optional[dict] = None


@dataclass(frozen=True)
class AddEdgePayload(Model):
    source_id: str
    target_id: str
    relation: str
    weight: Optional[float] = None


@dataclass(frozen=True)
class QueryGraphPayload(Model):
    node_id: Optional[str] = None
    type: Optional[str] = None
    relation: Optional[str] = None


def register_graph_function(sdk: IIIClient, kv: StateKV):
    async def handle_add_node(raw_data: dict):
        data = AddNodePayload.from_dict(raw_data)

        if not data.label or not data.label.strip():
            return {"success": False, "error": "label is required"}

        if not data.type or not data.type.strip():
            return {"success": False, "error": "type is required"}

        now = datetime.now(timezone.utc).isoformat()

        node = GraphNode(
            id=generate_id("node"),
            label=data.label,
            type=data.type,
            properties=data.properties or {},
            created_at=now,
            updated_at=now,
        )

        await kv.set(KV.graph_nodes, node.id, node)
        logger.info("Graph node added (id: %s, type: %s)", node.id, node.type)
        return {"success": True, "node": node}

    async def handle_add_edge(raw_data: dict):
        data = AddEdgePayload.from_dict(raw_data)

        if not data.source_id or not data.target_id:
            return {"success": False, "error": "source_id and target_id are required"}

        if not data.relation or not data.relation.strip():
            return {"success": False, "error": "relation is required"}

        now = datetime.now(timezone.utc).isoformat()

        edge = GraphEdge(
            id=generate_id("edge"),
            source_id=data.source_id,
            target_id=data.target_id,
            relation=data.relation,
            weight=data.weight if data.weight is not None else 1.0,
            created_at=now,
        )

        await kv.set(KV.graph_edges, edge.id, edge)
        logger.info("Graph edge added (id: %s, relation: %s)", edge.id, edge.relation)
        return {"success": True, "edge": edge}

    async def handle_query_graph(raw_data: dict):
        data = QueryGraphPayload.from_dict(raw_data)

        nodes: List[GraphNode] = await kv.list(KV.graph_nodes, GraphNode)
        edges: List[GraphEdge] = await kv.list(KV.graph_edges, GraphEdge)

        if data.node_id:
            nodes = [n for n in nodes if n.id == data.node_id]
            edges = [
                e for e in edges
                if e.source_id == data.node_id or e.target_id == data.node_id
            ]

        if data.type:
            nodes = [n for n in nodes if n.type == data.type]

        if data.relation:
            edges = [e for e in edges if e.relation == data.relation]

        logger.info("Graph query: %d nodes, %d edges", len(nodes), len(edges))
        return {"success": True, "nodes": nodes, "edges": edges}

    sdk.register_function({"id": "mem::graph-add-node"}, handle_add_node)
    sdk.register_function({"id": "mem::graph-add-edge"}, handle_add_edge)
    sdk.register_function({"id": "mem::graph-query"}, handle_query_graph)

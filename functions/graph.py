from dataclasses import dataclass
from datetime import datetime, timezone
import json
from typing import Dict, List
from logger import get_logger
from iii import IIIClient
from prompts.graph_extraction import GRAPH_EXTRACTION_SYSTEM, build_graph_extraction_prompt
from schema import CompressedObservation, MemoryProvider
from schema.domain import EdgeContext, GraphEdge, GraphNode
from state.kv import StateKV
from schema.base import Model
from state.schema import KV, generate_id

logger = get_logger("graph")


@dataclass(frozen=True)
class GraphExtractPayload(Model):
    observations: List[CompressedObservation]


@dataclass(frozen=True)
class ParsedGraph(Model):
    nodes: List[GraphNode]
    edges: List[GraphEdge]


def parse_graph_json(
    json_str: str,
    observation_ids: List[str],
) -> ParsedGraph:

    nodes: List[GraphNode] = []
    edges: List[GraphEdge] = []
    now = datetime.now(timezone.utc).isoformat()

    try:
        data = json.loads(json_str)
    except Exception as e:
        logger.warning("Failed to parse graph JSON: %s", e)
        return ParsedGraph(nodes=[], edges=[])

    entity_name_to_node: Dict[str, GraphNode] = {}

    # -----------------------------
    # Parse Entities → Nodes
    # -----------------------------
    for e in data.get("entities", []):
        name = e.get("name")
        node_type = e.get("type")

        if not name or not node_type:
            continue

        raw_aliases = e.get("aliases") or []
        aliases = [a for a in raw_aliases if isinstance(a, str) and a] or None

        node = GraphNode(
            id=generate_id("gn"),
            type=node_type,
            name=name,
            properties=e.get("properties", {}) or {},
            source_obs_ids=observation_ids,
            created_at=now,
            aliases=aliases,
        )

        nodes.append(node)
        entity_name_to_node[name] = node

    # -----------------------------
    # Parse Relationships → Edges
    # -----------------------------
    for r in data.get("relationships", []):
        rel_type = r.get("type")
        source_name = r.get("source")
        target_name = r.get("target")

        if not rel_type or not source_name or not target_name:
            continue

        source_node = entity_name_to_node.get(source_name)
        target_node = entity_name_to_node.get(target_name)

        if not source_node or not target_node:
            continue

        try:
            weight = float(r.get("weight", 0.5))
        except (TypeError, ValueError):
            weight = 0.5

        weight = max(0.0, min(1.0, weight))

        raw_ctx = r.get("context")
        edge_context: EdgeContext | None = None
        if isinstance(raw_ctx, dict):
            ctx_confidence = raw_ctx.get("confidence")
            if ctx_confidence is not None:
                try:
                    ctx_confidence = float(ctx_confidence)
                    ctx_confidence = max(0.0, min(1.0, ctx_confidence))
                except (TypeError, ValueError):
                    ctx_confidence = None
            edge_context = EdgeContext(
                reasoning=raw_ctx.get("reasoning") or None,
                sentiment=raw_ctx.get("sentiment") or None,
                alternatives=raw_ctx.get("alternatives") or None,
                confidence=ctx_confidence,
            )

        edge = GraphEdge(
            id=generate_id("ge"),
            type=rel_type,
            source_node_id=source_node.id,
            target_node_id=target_node.id,
            weight=weight,
            source_obs_ids=observation_ids,
            created_at=now,
            context=edge_context,
        )

        edges.append(edge)

    return ParsedGraph(nodes=nodes, edges=edges)


def register_graph_function(sdk: IIIClient, kv: StateKV, provider: MemoryProvider):
    async def handle_graph_extract(raw_data: dict):
        data = GraphExtractPayload.from_dict(raw_data)

        if not data.observations:
            return {"success": False, "error": "no observations provided"}

        prompt = build_graph_extraction_prompt(
            [
                {
                    "type": o.type,
                    "title": o.title,
                    "subtitle": o.subtitle,
                    "narrative": o.narrative,
                    "facts": o.facts,
                    "concepts": o.concepts,
                    "files": o.files,
                    "importance": o.importance,
                    "confidence": o.confidence,
                }
                for o in data.observations]
        )

        try:
            response = await provider.compress(GRAPH_EXTRACTION_SYSTEM, prompt)

            obs_ids = [o.id for o in data.observations]

            graph = parse_graph_json(response, obs_ids)
            existing_nodes = await kv.list(KV.graph_nodes, GraphNode)
            existing_edges = await kv.list(KV.graph_edges, GraphEdge)

            for node in graph.nodes:
                existing = next(
                    (
                        n for n in existing_nodes
                        if n.name == node.name and n.type == node.type
                    ), None)

                if existing:
                    merged = GraphNode(
                        id=existing.id,
                        type=existing.type,
                        name=existing.name,
                        properties={**existing.properties, **node.properties},
                        source_obs_ids=list(
                            set(existing.source_obs_ids + obs_ids)
                        ),
                        created_at=existing.created_at,
                    )

                    await kv.set(KV.graph_nodes, existing.id, merged)

                    idx = next(
                        (i for i, n in enumerate(existing_nodes)
                         if n.id == existing.id),
                        -1,
                    )
                    if idx != -1:
                        existing_nodes[idx] = merged
                else:
                    await kv.set(KV.graph_nodes, node.id, node)
                    existing_nodes.append(node)

            for edge in graph.edges:
                edge_key = f"{edge.source_node_id}|{edge.target_node_id}|{edge.type}"

                existing_edge = next(
                    (
                        e
                        for e in existing_edges
                        if f"{e.source_node_id}|{e.target_node_id}|{e.type}" == edge_key
                    ),
                    None,
                )

                if existing_edge:
                    merged_edge = GraphEdge(
                        id=existing_edge.id,
                        type=existing_edge.type,
                        source_node_id=existing_edge.source_node_id,
                        target_node_id=existing_edge.target_node_id,
                        weight=existing_edge.weight,
                        source_obs_ids=list(
                            set(existing_edge.source_obs_ids + obs_ids)
                        ),
                        created_at=existing_edge.created_at,
                        tcommit=existing_edge.tcommit,
                        tvalid=existing_edge.tvalid,
                        tvalid_end=existing_edge.tvalid_end,
                        context=existing_edge.context,
                        version=existing_edge.version,
                        superseded_by=existing_edge.superseded_by,
                        is_latest=existing_edge.is_latest,
                        stale=existing_edge.stale,
                    )

                    await kv.set(KV.graph_edges, existing_edge.id, merged_edge)

                    idx = next(
                        (i for i, e in enumerate(existing_edges)
                         if e.id == existing_edge.id),
                        -1,
                    )
                    if idx != -1:
                        existing_edges[idx] = merged_edge
                else:
                    await kv.set(KV.graph_edges, edge.id, edge)
                    existing_edges.append(edge)

            logger.info("Graph extraction complete")

            return {
                "success": True,
                "nodes_added": len(graph.nodes),
                "edges_added": len(graph.edges),
            }

        except Exception as err:
            logger.warning("Failed to parse graph response (error: %s)", {
                "error": err
            })
            return {"success": False, "error": "graph_extracted_parsing_failed"}

    async def handle_graph_stats(raw_data: dict):
        nodes = await kv.list(KV.graph_nodes, GraphNode)
        edges = await kv.list(KV.graph_edges, GraphEdge)

        nodes_by_type: dict[str, int] = {}
        for n in nodes:
            nodes_by_type[n.type] = nodes_by_type.get(n.type, 0) + 1

        edges_by_type: dict[str, int] = {}
        for e in edges:
            edges_by_type[e.type] = edges_by_type.get(e.type, 0) + 1

        return {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "nodes_by_type": nodes_by_type,
            "edges_by_type": edges_by_type,
        }

    sdk.register_function({"id": "mem::graph_extract"}, handle_graph_extract)
    sdk.register_function({"id": "mem::graph_stats"}, handle_graph_stats)

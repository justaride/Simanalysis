"""Dependency graph utilities."""

from __future__ import annotations

import networkx as nx

from .resources import TuningNode


class DepGraph:
    """Simple directed graph for tuning dependencies."""

    def __init__(self) -> None:
        self._nodes: dict[str, TuningNode] = {}
        self._edges: set[tuple[str, str]] = set()

    def add_node(self, node: TuningNode) -> None:
        self._nodes[node.tuning_id] = node

    def add_edge(self, src_id: str, dst_id: str) -> None:
        if src_id and dst_id:
            self._edges.add((src_id, dst_id))

    def to_networkx(self) -> nx.DiGraph:
        graph = nx.DiGraph()
        for node_id, node in self._nodes.items():
            graph.add_node(node_id, tuning_type=node.tuning_type)
        for src, dst in self._edges:
            if dst not in graph:
                graph.add_node(dst, tuning_type="unknown")
            graph.add_edge(src, dst)
        return graph

    def to_json(self) -> dict[str, list[dict[str, str]]]:
        nodes: dict[str, dict[str, str]] = {
            node_id: {"id": node_id, "tuning_type": node.tuning_type}
            for node_id, node in self._nodes.items()
        }
        edges_list: list[dict[str, str]] = []
        for src, dst in sorted(self._edges):
            if dst not in nodes:
                nodes[dst] = {"id": dst, "tuning_type": "unknown"}
            edges_list.append({"source": src, "target": dst})
        nodes_list = [nodes[node_id] for node_id in sorted(nodes)]
        return {"nodes": nodes_list, "edges": edges_list}

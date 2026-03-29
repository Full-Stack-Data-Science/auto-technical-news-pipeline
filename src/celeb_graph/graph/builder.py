import networkx as nx
from celeb_graph.models import RelationshipModel, RelationType

def build_graph(relationships: RelationshipModel) -> nx.MultiDiGraph:
    """
    Convert a :class:`RelationshipModel` into a NetworkX ``MultiDiGraph``.
    """
    graph = nx.MultiDiGraph()

    for user, relation_map in relationships.to_dict().items():
        graph.add_node(user, node_type="user")

        for relation_type in RelationType:
            for target in relation_map.get(relation_type.value, set()):
                graph.add_node(target, node_type="user")
                graph.add_edge(user, target, relation=relation_type.value)

    return graph


def filter_by_relation(
    graph: nx.MultiDiGraph,
    relation: RelationType,
) -> nx.DiGraph:
    """
    Return a simple directed graph containing only edges of *relation* type.
    Useful for running algorithms (e.g. PageRank) on a single relation layer.
    """
    subgraph = nx.DiGraph()
    subgraph.add_nodes_from(graph.nodes(data=True))

    for u, v, data in graph.edges(data=True):
        if data.get("relation") == relation.value:
            subgraph.add_edge(u, v)

    return subgraph
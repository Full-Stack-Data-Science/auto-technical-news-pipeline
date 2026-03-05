import networkx as nx

from network.relation import RelationshipModel, RelationType

def build_nx_graph(
    relationships: RelationshipModel,
) -> nx.MultiDiGraph:
    """
    Convert the relationship model into a NetworkX MultiDiGraph.
    """
    relations = relationships.to_dict()
    graph = nx.MultiDiGraph()

    for user, relation_map in relations.items():
        graph.add_node(user, node_type="user")

        for relation_type in RelationType:
            targets = relation_map.get(relation_type.value, set())

            for target in targets:
                graph.add_node(target, node_type="user")
                graph.add_edge(
                    user,
                    target,
                    relation=relation_type.value,
                )

    return graph
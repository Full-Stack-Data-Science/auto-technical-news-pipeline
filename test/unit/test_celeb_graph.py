from celeb_graph.models.relationship import RelationshipModel, RelationType, Relation
from celeb_graph.io.json_loader import load_from_json, dump_to_json
from celeb_graph.graph.builder import build_graph
import networkx as nx
import unittest

class TestNetworkRelationModelBuidler(unittest.TestCase):
    def test_simple_relation(self):
        r = Relation("alice", RelationType.FOLLOW, "bob")
        assert r.source        == "alice"
        assert r.relation_type == RelationType.FOLLOW
        assert r.target        == "bob"

    def test_empty_relation(self):
        model = RelationshipModel()
        self.assertEqual({}, model.to_dict())
        
    def test_add_stores_correct_target(self):
        model = RelationshipModel()

        model.add(Relation("alice", RelationType.FOLLOW,  "bob"))
        model.add(Relation("hung", RelationType.FOLLOW,  "carol"))
        model.add(Relation("alice", RelationType.MENTION, "bob"))
        model.add(Relation("bob",   RelationType.FOLLOW,  "alice"))

        self.assertEqual({
            "alice": {"follow": ["bob"],   "mention": ["bob"]},
            "bob": {"follow": ["alice"], "mention": []},
            "hung": {"follow": ["carol"], "mention": []},
            "carol": {"follow": [],        "mention": []},
        }, model.to_dict())
        
    def test_from_dict(self):
        # basic structure
        model = RelationshipModel.from_dict({
            "alice": {"follow": ["bob", "carol"], "mention": ["dave"]},
            "bob":   {"follow": ["carol"],        "mention": []},
            "carol": {"follow": [],               "mention": ["alice"]},
        })
        self.assertEqual({
            "alice": {"follow": ["bob", "carol"], "mention": ["dave"]},
            "bob":   {"follow": ["carol"],        "mention": []},
            "carol": {"follow": [],               "mention": ["alice"]},
            "dave":  {"follow": [],               "mention": []},  # implicit target node
        }, model.to_dict())


    def test_build_graph(self):
        model = RelationshipModel.from_dict({
            "alice": {"follow": ["bob"], "mention": []},
            "bob":   {"follow": [],     "mention": []},
        })
        graph = build_graph(model)

        self.assertIsInstance(graph, nx.MultiDiGraph)
        self.assertIn("alice", graph.nodes)
        self.assertIn("bob", graph.nodes)
        self.assertTrue(graph.has_edge("alice", "bob"))

    def test_json_loader(self):
        import tempfile, pathlib
        model = RelationshipModel.from_dict({
            "alice": {"follow": ["bob"], "mention": []},
            "bob":   {"follow": [],     "mention": []},
        })
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "test.json"
            dump_to_json(model, path)
            loaded = load_from_json(path)

        self.assertEqual(model.to_dict(), loaded.to_dict())
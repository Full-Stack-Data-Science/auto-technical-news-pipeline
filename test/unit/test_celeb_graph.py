from celeb_graph.models.relationship import RelationshipModel, RelationType, Relation
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


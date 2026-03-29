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
        model.add(Relation("alice", RelationType.FOLLOW, "bob"))
        assert "bob" in model.to_dict()["alice"]["follow"]
 
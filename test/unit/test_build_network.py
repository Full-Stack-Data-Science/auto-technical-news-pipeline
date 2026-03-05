from network.relation import RelationshipModel, RelationType
import unittest

class TestNetworkRelationModelBuidler(unittest.TestCase):
    def test_empty_relation(self):
        model = RelationshipModel()
        self.assertEqual({}, model.to_dict())
    
    def test_not_empty_relation(self):
        model = RelationshipModel()
        model.add(RelationType.FOLLOW, "user_1", "user_2")
        model.add(RelationType.MENTION, "user_2", "user_3")
        expected = {
            "user_1":{
                "follow":{"user_2"},
                "mention":set(),
            },
            "user_2":{
                "follow":set(),
                "mention":{"user_3"},
            },
            "user_3":{
                "follow":set(),
                "mention":set(),
            },
        }

        self.assertEqual(expected, model.to_dict())

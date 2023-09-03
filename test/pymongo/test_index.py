#!/usr/bin/env python3
import unittest
from bson.son import SON

from .. import utils

EMAIL_INDEX = {"key": SON([("email", 1)]), "name": "email_1", "unique": True, "v": 2}
OBJ_INDEX = {"key": SON([("_id", 1)]), "name": "_id_", "v": 2}

INDEXES = SON[EMAIL_INDEX, OBJ_INDEX]


class TestFind(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        utils.drop_database()

    @classmethod
    def tearDownClass(cls) -> None:
        utils.drop_database()

    def test_all_index(self) -> None:
        client = utils.create_client()
        User = utils.create_class("user", client)

        user = User("John Howard", "john@gmail.com", 8771, "PH")
        user.insert()
        self.assertEqual([{'email': 'john@gmail.com'}], list(user.find({}, {"email": 1, "_id": 0})))
        rv = user.createIndex("email")
        self.assertEqual("email_1", rv)
        self.assertEqual(EMAIL_INDEX, list(user.getIndexes())[1])
        self.assertEqual("email", user.indexName)
        self.assertEqual("john@gmail.com", user.indexValue)


if __name__ == "__main__":
    unittest.main()

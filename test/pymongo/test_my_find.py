#!/usr/bin/env python3
import unittest

from .. import utils


class TestFind(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        utils.drop_database()

    @classmethod
    def tearDownClass(cls) -> None:
        utils.drop_database()

    def test_getIndexes(self) -> None:
        client = utils.create_client()
        User = utils.create_class("user", client)

        user = User("John Howard", "john@gmail.com", 8771, "PH")
        user.insert()
        self.assertEqual([{'email': 'john@gmail.com'}], list(user.find({}, {"email": 1, "_id": 0})))


if __name__ == "__main__":
    unittest.main()

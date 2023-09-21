import unittest

from pymongo import MongoClient
from pymongo.database import Database

from .. import utils

DB_NAME = "mongoclass-test"
DB_MONGODB_NAME = DB_NAME + "-mongodb"


class TestFind(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        utils.drop_database()
        utils.drop_database(DB_MONGODB_NAME)

    @classmethod
    def tearDownClass(cls) -> None:
        utils.drop_database()
        utils.drop_database(DB_MONGODB_NAME)

    # noinspection PyPep8Naming
    def test_mongodb(self) -> None:
        client = utils.create_client()
        User = utils.create_class("user", client)
        user = User("John Howard", "john@gmail.com", 8771, "PH")
        self.assertIsInstance(user.mongodb_client, MongoClient)
        self.assertIsInstance(user.mongodb_db, Database)
        self.assertEqual(user.mongodb_db.name, "mongoclass-test")
        inserted = user.insert()
        self.assertNotEqual(inserted, {})
        self.assertEqual(inserted, user.one())

        user.mongodb_db = DB_MONGODB_NAME
        self.assertIsNone(user.one())


if __name__ == "__main__":
    unittest.main()

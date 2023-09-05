import unittest
from bson.son import SON

from mongoclass import is_testing
from .. import utils

EMAIL_INDEX = {"key": SON([("email", 1)]), "name": "email_1", "unique": True, "v": 2}
OBJ_INDEX = {"key": SON([("_id", 1)]), "name": "_id_", "v": 2}

INDEXES = SON[EMAIL_INDEX, OBJ_INDEX]


# noinspection PyPep8Naming
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
        self.assertEqual(is_testing(), True)
        self.assertIn("-test", user.DATABASE_NAME)


if __name__ == "__main__":
    unittest.main()

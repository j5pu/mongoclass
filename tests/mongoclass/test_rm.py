import unittest

from .. import utils


# noinspection PyPep8Naming
class TestFind(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        utils.drop_database()

    @classmethod
    def tearDownClass(cls) -> None:
        utils.drop_database()

    def test_one(self) -> None:
        client = utils.create_client()
        User = utils.create_class("user", client)

        user = User("John Howard", "john@gmail.com", 8771, "PH")
        user.insert()
        self.assertTrue(user.has())
        user.rm()
        self.assertFalse(user.has())


if __name__ == "__main__":
    unittest.main()

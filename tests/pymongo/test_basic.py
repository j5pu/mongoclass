import unittest
from dataclasses import dataclass

from mongodata import is_testing
from .. import utils


class TestBasic(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        utils.drop_database()

    @classmethod
    def tearDownClass(cls) -> None:
        utils.drop_database()

    def test_wrap(self) -> None:
        client = utils.create_client()
        User = utils.create_class("user", client)
        self.assertEqual(User.__name__, "User")

    def test_basic(self) -> None:
        client = utils.create_client()

        if is_testing():
            self.assertEqual(client.default_database.name, "mongoclass-test")
        else:
            self.assertEqual(client.default_database.name, "mongoclass")

        self.assertEqual(client.mapping, {})
        client.server_info()

    def test_as_json(self) -> None:
        client = utils.create_client()

        @client.mongoclass()
        @dataclass
        class NameInformation:
            first: str
            last: str

        @client.mongoclass()
        @dataclass
        class Metadata:
            name: NameInformation

        @client.mongoclass()
        @dataclass
        class User:
            email: str
            metadata: Metadata

            def message(self) -> None:
                pass

        # Test for nested disbaled
        metadata = Metadata(NameInformation("Trevor", "Warts"))
        john = User("trevor@gmail.com", metadata)
        self.assertEqual(
            john.as_json(), {"email": "trevor@gmail.com", "metadata": metadata}
        )

    def test_decorator(self) -> None:
        client = utils.create_client()
        default_database = client.default_database.name

        # Test decorator methods exists
        Position = utils.create_class("position", client)
        getattr(Position, "insert")
        getattr(Position, "update")

        # Test decorator attributes on init
        coordinates = Position(1, 2, 3)
        self.assertEqual(coordinates._mongodb_collection, "position")
        self.assertEqual(coordinates._mongodb_db, client.default_database)

        # Check classes mapping
        self.assertEqual(
            client.mapping,
            {
                default_database: {
                    "position": {"constructor": Position, "nested": False}
                }
            },
        )

        ProfileObject = utils.create_class("user", client, "profile")
        john = ProfileObject("john howard", "john@gmail.com", 1234)
        self.assertEqual(john._mongodb_collection, "profile")
        self.assertEqual(john._mongodb_db, client.default_database)

        # Check classes mapping
        self.assertEqual(
            client.mapping,
            {
                default_database: {
                    "position": {"constructor": Position, "nested": False},
                    "profile": {"constructor": ProfileObject, "nested": False},
                }
            },
        )

        # Provide a different database and check if that matches
        User = utils.create_class("user", client, database=utils.DATABASES[2])
        tony = User("Tony Howards", "tony@gmail.com", 123456)
        self.assertEqual(tony._mongodb_db.name, utils.DATABASES[2])

        # Check classes mapping
        self.assertDictEqual(
            client.mapping,
            {
                default_database: {
                    "position": {"constructor": Position, "nested": False},
                    "profile": {"constructor": ProfileObject, "nested": False},
                },
                utils.DATABASES[2]: {"user": {"constructor": User, "nested": False}},
            },
        )


if __name__ == "__main__":
    unittest.main()

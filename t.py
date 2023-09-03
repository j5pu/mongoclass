import dataclasses
from typing import Generic
from typing import TypeVar

from mongoclass import MongoClassClient
from mongoclass.client import SupportsMongoClass

client = MongoClassClient("test", "mongodb://localhost:27017/")


@client.mongoclass()
@dataclasses.dataclass
class User(SupportsMongoClass):
    num: int = 0


user = User()
print(user.collection)
print(user.insert())
print(user.rm())
print(user.one())
print(user.exists())


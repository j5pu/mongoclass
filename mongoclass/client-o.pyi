from typing import Any
from typing import Callable
from typing import Generic
from typing import Optional
from typing import Protocol
from typing import TypeVar
from typing import Union

import mongita
import mongita
import pymongo
from pymongo.database import Database
import pymongo.results
from bson import ObjectId
from mongita import MongitaClientDisk
from mongita import MongitaClientMemory
from pymongo import MongoClient

from .cursor import Cursor as Cursor

T = TypeVar("T", bound=object)
MongoClassType = Union[Callable, MongoClassClient, MongoClient, MongitaClientDisk, MongitaClientMemory]


class MongoClassClientClass(MongoClient, MongitaClientDisk, MongitaClientMemory):
    def __init__(self, default_db_name: str = ..., *args: Any, **kwargs: Any) -> None: ...

    def __choose_database(
            self,
            database: Optional[
                Union[str, pymongo.database.Database, mongita.database.Database]
            ] = ...,
    ) -> Union[pymongo.database.Database, mongita.database.Database]: ...

    def __getitem__(
            self,
            database: Union[str, pymongo.database.Database, mongita.database.Database],
    ) -> Union[pymongo.database.Database, mongita.database.Database]: ...

    def get_db(
            self, database: str
    ) -> Union[pymongo.database.Database, mongita.database.Database]: ...

    def map_document(
            self, data: dict, collection: str, database: str, force_nested: bool = False
    ) -> object: ...

    def mongoclass(
            self,
            collection: Optional[str] = ...,
            database: Optional[Union[str, pymongo.database.Database]] = ...,
            insert_on_init: bool = ...,
            nested: bool = ...,
    ) -> Union[Callable, MongoClassType]: ...


def client_constructor(engine: str, *args, test: bool = ..., **kwargs) -> MongoClassClientClass: ...


def MongoClassClient(*args, test: bool = ..., **kwargs) -> MongoClassClientClass: ...

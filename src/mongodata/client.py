"""Mongo Data Class Client Module."""
from __future__ import annotations

__all__ = (
    "CONSOLE",
    "MONGOCLASS_TEST_SUFFIX",
    "atlas_add_ip",
    "atlas_api",
    "client_mongoclass",
    "client_pymongo",
    "is_testing",
    "mongo_url",
    "run_if_production",
    "run_in_production",
    "SupportsMongoClass",
    "SupportsMongoClassClient",
    "client_constructor",
    "MongoClassClient",
)

import contextlib
import copy
import dataclasses
import functools
import inspect
import json
import os
import warnings
from typing import TYPE_CHECKING, Any, Protocol

import furl
import mongita.database
import mongita.results
import nodeps
import pymongo.collection
import pymongo.database
import pymongo.results
import requests
import rich.pretty
import rich.traceback
from furl.common import absent as _absent
from mongita import MongitaClientDisk, MongitaClientMemory
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from requests.auth import HTTPDigestAuth

from .cursor import Cursor

if TYPE_CHECKING:
    from collections.abc import Callable, MutableMapping

    from bson import ObjectId
    from pymongo.command_cursor import CommandCursor
    from pymongo.results import UpdateResult

CONSOLE = rich.console.Console(force_interactive=True, color_system='256')
MONGOCLASS_TEST_SUFFIX = "-test"
"""suffix to add to database name"""

rich.pretty.install(CONSOLE, expand_all=True)
rich.traceback.install(show_locals=True)


class MongoDataError(Exception):
    """Base class for exceptions in this module."""


def atlas_api(url, query: dict | None = None, user: str | None = None,
              password: str | None = None, payload=None) -> dict | None:
    """Atlas API.

    Examples:
        >>> from mongodata.client import atlas_api
        >>>
        >>> atlas_api("groups")  # doctest: +ELLIPSIS
        {'links': [{'href': '...', 'rel': 'self'}], 'results': [{'clusterCount': 1, 'created': '2023-09-02T08:30:14Z',\
 'id': '...', 'links': [{'href': '...', 'rel': 'self'}], 'name': 'pdf', 'orgId': '...'}], 'totalCount': ...}

    Args:
        url: url
        query: query
        user: user
        password: password
        payload: payload
    """
    user = user if user else os.environ.get("ATLAS_PUBLIC_KEY_MNOPI")
    password = password if password else os.environ.get("ATLAS_PRIVATE_KEY_MNOPI")
    if user is None or password is None:
        msg = f"user and password must be set or pass as arguments: {user=}, {password=}"
        raise MongoDataError(msg)

    url = furl.furl(f"https://cloud.mongodb.com/api/atlas/v2/{url}",
                    query=(query or {}) | {
                        "envelope": False, "includeCount": True, "itemsPerPage": 100, "pageNum": 1, "pretty": False
                    })

    function = requests.post if payload else requests.get
    return function(url.url, auth=HTTPDigestAuth(user, password),
                    headers={
                        "Accept": "application/vnd.atlas.2023-01-01+json",
                        'Content-Type': 'application/vnd.atlas.2023-01-01+json'
                    }, data=payload).json()


def atlas_add_ip(project: str) -> dict | None:
    """Add ip to project.

    Examples:
        >>> from mongodata.client import atlas_add_ip
        >>>
        >>> atlas_add_ip("pdf",)  # doctest: +ELLIPSIS
        {'links': [{'href': '...', 'rel': 'self'}], 'results': [{'cidrBlock': '...', 'comment': 'My IP Address',\
 'groupId': '...', 'ipAddress': '...', 'links': [{'href': '...', 'rel': 'self'}]}...'totalCount': ...}

    """
    group_id = None
    groups = atlas_api("groups")

    for item in groups["results"]:
        if item["name"] == project:
            group_id = item["id"]
            break
    if group_id is None:
        msg = f"{project=} not found"
        raise MongoDataError(msg)

    payload = json.dumps([{"cidrBlock": f"{nodeps.mip()}/32"}])

    return atlas_api(f"groups/{group_id}/accessList", payload=payload)


def client_mongoclass(
        atlas: bool = True,
        db: str = "main",
        host: str = _absent,
        password: str = _absent,
        port: str | int = _absent,
        query: dict = _absent,
        scheme: dict = _absent,
        username: str = _absent,
) -> SupportsMongoClassClient | (MongoClient | pymongo.database.Database):
    """Returns a MongoClient.

    Examples:
        >>> from mongodata.client import client_mongoclass
        >>>
        >>> client = client_mongoclass(db="pdf")
        >>> client  # doctest: +ELLIPSIS
        MongoClient(host=['....mongodb.net:27017', '....mongodb.net:27017', '....mongodb.net:27017'],\
 document_class=dict, tz_aware=False, connect=True,\
 retrywrites=True, w='majority', authsource='admin',\
 replicaset='...shard-0', tls=True)
        >>> client.default_database  # doctest: +ELLIPSIS
        Database(MongoClient(host=['....mongodb.net:27017', '....mongodb.net:27017',\
 '....mongodb.net:27017'], document_class=dict, tz_aware=False, connect=True, retrywrites=True,\
 w='majority', authsource='admin', replicaset='...shard-0', tls=True), 'pdf-test')
        >>> client_mongoclass(atlas=False)  # doctest: +ELLIPSIS
        MongoClient(host=['localhost:27017'], document_class=dict, tz_aware=False, connect=True)

    Args:
        atlas: True if atlas url to use atlas defaults
        db: database (Defaults: main)
        host: cluster/host/domain
        password: password
        port: port (Default: 27017)
        query: query (Default: {"retryWrites": true, "w": "majority"})
        scheme: scheme (Default: mongodb+srv)
        username: user

    Returns:
        MongoClient
    """
    return MongoClassClient(
        db,
        mongo_url(atlas=atlas, host=host, password=password, port=port, query=query, scheme=scheme, username=username)
    )


def client_pymongo(
        atlas: bool = True,
        host: str = _absent,
        password: str = _absent,
        port: str | int = _absent,
        query: dict = _absent,
        scheme: dict = _absent,
        username: str = _absent,
) -> MongoClient:
    """Returns a MongoClient.

    Examples:
        >>> from mongodata.client import client_pymongo
        >>>
        >>> client_pymongo()  # doctest: +ELLIPSIS
        MongoClient(host=['...:...', '....mongodb.net:27017', '....mongodb.net:27017'],\
 document_class=dict, tz_aware=False, connect=True, retrywrites=True, w='majority', authsource='admin',\
 replicaset='...', tls=True)
        >>> client_pymongo(atlas=False)  # doctest: +ELLIPSIS
        MongoClient(host=['localhost:27017'], document_class=dict, tz_aware=False, connect=True)

    Args:
        atlas: True if atlas url to use atlas defaults
        host: cluster/host/domain
        password: password
        port: port (Default: 27017)
        query: query (Default: {"retryWrites": true, "w": "majority"})
        scheme: scheme (Default: mongodb+srv)
        username: user

    Returns:
        MongoClient
    """
    return MongoClient(
        mongo_url(atlas=atlas, host=host, password=password, port=port, query=query, scheme=scheme, username=username)
    )


def is_testing() -> bool:
    """True if global `MONGOCLASS_PRODUCTION` is None or any: pytest, docrunner, unittest, PyCharm in callers filenames.

    Examples:
        >>> from mongodata.client import is_testing
        >>>
        >>> is_testing()
        True

    """
    if os.environ.get("MONGOCLASS_PRODUCTION"):
        return False
    for f in inspect.stack():
        if "pytest" in f.filename or "docrunner" in f.filename or "unittest" in f.filename or "PyCharm" in f.filename:
            return True
    return False


def mongo_url(
        atlas: bool = True,
        host: str = _absent,
        password: str = _absent,
        port: str | int = _absent,
        query: dict = _absent,
        scheme: dict = _absent,
        username: str = _absent,
) -> str:
    """Returns atlas url for connection.

    Examples:
        >>> from mongodata.client import mongo_url
        >>>
        >>> mongo_url()  # doctest: +ELLIPSIS
        'mongodb+srv://...:...@....mongodb.net/?retryWrites=true&w=majority'
        >>> mongo_url(atlas=False)
        'mongodb://localhost:27017'

    Args:
        atlas: True if atlas url to use atlas defaults
        host: cluster/host/domain
        password: password
        port: port (Default: 27017)
        query: query (Default: {"retryWrites": true, "w": "majority"})
        scheme: scheme (Default: mongodb+srv)
        username: user

    """
    if atlas:
        host = "cluster0.xxjqsmg.mongodb.net" if host is _absent else host
        password = os.environ.get("ATLAS_PASSWORD") if password is _absent else password
        query = {"retryWrites": "true", "w": "majority"} if query is _absent else query
        scheme = "mongodb+srv" if scheme is _absent else scheme
        username = os.environ.get("ATLAS_USER") if username is _absent else username
    else:
        host = "localhost" if host is _absent else host
        port = 27017 if port is _absent else port
        scheme = "mongodb" if scheme is _absent else scheme
    return furl.furl(
        host=host, password=password, port=port, query=query, scheme=scheme, username=username
    ).url.replace("?", "/?")


def run_if_production(func):
    """A decorator that will run the function if TESTING is False.

    Examples:
        >>> from mongodata.client import is_testing
        >>> from mongodata.client import run_if_production
        >>> from mongodata.client import run_in_production
        >>>
        >>> @run_if_production
        ... def hello():
        ...    return is_testing()
        >>>
        >>> hello()
        >>>
        >>> with run_in_production():
        ...     hello()
        False
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if is_testing():
            return None
        return func(*args, **kwargs)

    return wrapper


@contextlib.contextmanager
def run_in_production():
    """A context manager that will set TESTING to False.

    Examples:
        >>> with run_in_production():
        ...     is_testing()
        False
    """
    os.environ["MONGOCLASS_PRODUCTION"] = "1"
    yield
    del os.environ["MONGOCLASS_PRODUCTION"]


class SupportsMongoClass(Protocol):
    """SupportsMongoClass protocol."""
    COLLECTION_NAME: str
    DATABASE_NAME: str
    _mongodb_collection: str
    _mongodb_client: MongoClient | (MongitaClientDisk | MongitaClientMemory)
    _mongodb_db: pymongo.database.Database | mongita.database.Database
    _mongodb_id: ObjectId

    @property
    def collection(self) -> pymongo.collection.Collection:  # noqa: D102
        return ...

    def createIndex(self, field: str): ...  # noqa: D102, N802

    def distinct(self, field: str, query: dict) -> list[str | (int | (dict | list))]: ...  # noqa: D102

    def find(self, *args, **kwargs) -> Cursor: ...  # noqa: D102

    def getIndexes(self) -> CommandCursor[MutableMapping[str, Any]]: ...  # noqa: D102, N802

    def has(self) -> bool: ...  # noqa: D102

    @property
    def id(self) -> ObjectId:  # noqa: D102, A003
        return ...

    @property
    def indexName(self) -> str | None:  # noqa: D102, N802
        return ...

    @property
    def indexValue(self) -> int | (str | (dict | list)):  # noqa: D102, N802
        return ...

    @property
    def mongodb_client(self) -> MongoClient | (MongitaClientDisk | MongitaClientMemory):  # noqa: D102
        return ...

    @property
    def mongodb_db(self) -> pymongo.database.Database | mongita.database.Database:  # noqa: D102
        return ...

    @mongodb_db.setter
    def mongodb_db(self, value: str | pymongo.database.Database | None):
        ...

    def one(self) -> dict | None: ...  # noqa: D102

    def rm(self) -> pymongo.results.DeleteResult | mongita.results.DeleteResult: ...  # noqa: D102

    def insert(self, *args, **kwargs) -> dict: ...  # noqa: D102

    def update(  # noqa: D102
            self,
            operation: dict,
            *args,
            **kwargs
    ) -> tuple[
        UpdateResult | mongita.results.UpdateResult, object,
    ]: ...

    def save(  # noqa: D102
            self,
            *args,
            **kwargs
    ) -> tuple[
        UpdateResult | (pymongo.results.InsertOneResult |
                        (mongita.results.InsertOneResult | mongita.results.UpdateResult)),
        object,
    ]: ...

    def delete(self, *args, **kwargs) -> pymongo.results.DeleteResult | mongita.results.DeleteResult: ...  # noqa: D102

    @staticmethod
    def count_documents(*args, **kwargs) -> int: ...  # noqa: D102

    @staticmethod
    def find_class(  # noqa: D102
            *args, database: str | (pymongo.database.Database | mongita.database.Database) | None = ...,
            **kwargs,
    ) -> object | None: ...

    find_one = find_class

    @staticmethod
    def aggregate(  # noqa: D102
            *args,
            database: str | (pymongo.database.Database | mongita.database.Database) | None = ...,
            **kwargs,
    ) -> Cursor: ...

    @staticmethod
    def paginate(  # noqa: D102
            *args,
            database: str | (pymongo.database.Database | mongita.database.Database) | None = ...,
            pre_call: Callable = ...,
            page: int,
            size: int,
            **kwargs,
    ) -> Cursor: ...

    @staticmethod
    def find_classes(  # noqa: D102
            *args,
            database: str | (pymongo.database.Database | mongita.database.Database) | None = ...,
            **kwargs,
    ) -> Cursor: ...

    def as_json(self, perform_nesting: bool = ...) -> dict: ...  # noqa: D102

    def insert_classes(  # noqa: D102
            self, mongoclasses: object | list[object], *args, **kwargs
    ) -> pymongo.results.InsertOneResult | (pymongo.results.InsertManyResult |
                                            list[pymongo.results.InsertOneResult]): ...

    insert_many = insert_classes


class SupportsMongoClassClient(Protocol):
    """SupportsMongoClassClient protocol."""
    mapping: dict = ...
    default_database: pymongo.database.Database
    _default_db_name: str = ...

    @property
    def default_db_name(self) -> str:  # noqa: D102
        return ...

    @default_db_name.setter
    def default_db_name(self, value: str) -> None: ...

    def choose_database(  # noqa: D102
            self,
            database: str | (pymongo.database.Database | mongita.database.Database) | None = ...
    ) -> pymongo.database.Database | mongita.database.Database: ...

    def get_db(self, database: str) -> pymongo.database.Database | mongita.database.Database: ...  # noqa: D102

    def map_document(  # noqa: D102
            self,
            data: dict,
            collection: str,
            database: str,
            force_nested: bool = ...
    ) -> object: ...

    def mongoclass(  # noqa: D102
            self,
            collection: str | None = ...,
            database: str | pymongo.database.Database | None = ...,
            insert_on_init: bool = ...,
            nested: bool = ...,
    ) -> Callable | SupportsMongoClass: ...

    def find_class(  # noqa: D102
            self,
            collection: str,
            *args,
            database: str | (pymongo.database.Database | mongita.database.Database) | None = ...,
            **kwargs,
    ) -> object | None: ...

    def find_classes(  # noqa: D102
            self,
            collection: str,
            *args,
            database: str | (
                    pymongo.database.Database | mongita.database.Database) | None = ...,
            **kwargs,
    ) -> Cursor: ...

    def insert_classes(  # noqa: D102
            self,
            mongoclasses: object | (pymongo.collection.Collection | list[object]),
            *args,
            **kwargs
    ) -> pymongo.results.InsertOneResult | (pymongo.results.InsertManyResult | list[
        pymongo.results.InsertOneResult]): ...

    insert_many = insert_classes


# noinspection PyPep8Naming
def client_constructor(  # noqa: D103
        engine: str,
        *args,
        **kwargs
) -> SupportsMongoClassClient | MongoClient | pymongo.database.Database:
    if engine == "pymongo":
        engine = MongoClient
    elif engine == "mongita_disk":
        engine = MongitaClientDisk
    elif engine == "mongita_memory":
        engine = MongitaClientMemory
    else:
        msg = f"Invalid engine '{engine}'"
        raise ValueError(msg)

    # noinspection PyShadowingNames
    class MongoClassClientClass(engine):
        """Mongo Class Client.

        Arguments:
            default_db_name: The name of the default database.
            *args: To be passed onto `MongoClient()` or `MongitaClientDisk()`
            **kwargs: To be passed onto `MongoClient()` or `MongitaClientDisk()`
        """

        def __init__(self, default_db_name: str = "main", *args, **kwargs) -> None:
            super().__init__(*args, **kwargs)
            self.mapping = {}
            self.default_db_name = default_db_name

            self.default_database: pymongo.database.Database | mongita.database.Database = self[self.default_db_name]

            # Determine engine being used
            self._engine_used = engine

        @property
        def default_db_name(self) -> str:
            """Get the name of the default database.

            Returns:
                The name of the default database.
            """
            return self._default_db_name

        @default_db_name.setter
        def default_db_name(self, value: str) -> None:
            """Sets default database name based on whether is testing."""
            if is_testing():
                self._default_db_name = value if MONGOCLASS_TEST_SUFFIX in value else f"{value}{MONGOCLASS_TEST_SUFFIX}"
            else:
                self._default_db_name = value.replace(MONGOCLASS_TEST_SUFFIX, "")

        def __choose_database(
                self,
                database: str | (pymongo.database.Database | mongita.database.Database) | None = None,
        ) -> pymongo.database.Database | mongita.database.Database:
            if database is None:
                return self.default_database
            if isinstance(
                    database, (pymongo.database.Database | mongita.database.Database)
            ):
                return database
            return self[database]

        choose_database = __choose_database

        def get_db(
                self, database: str
        ) -> pymongo.database.Database | mongita.database.Database:
            """Get a database. Equivalent to `client["database"]`.

            This method exists simply because type hinting seems to be broken, nothing more

            Arguments:
                database: str The name of the database.

            Returns:
                The `Database` object of the underlying engine.
            """
            return self[database]

        def map_document(
                self, data: dict, collection: str, database: str, force_nested: bool = False
        ) -> object:
            """Map a raw document into a mongoclass.

            Arguments:
                data: The raw document coming from a collection.
                collection: The collection this maps to. The collection then maps onto an actual mongoclass object.
                database: The database the raw document belongs to.
                force_nested: Forcefully tell mongoclass that this document is a nested document
                    and it contains other mongoclasses inside it. Defaults to False.
                    Usually this parameter is only set in a recursive manner.
            """
            cls = self.mapping[database][collection]
            if cls["nested"] or force_nested:
                for k, v in copy.copy(data).items():
                    if isinstance(v, dict):
                        if "_nest_collection" in v:
                            data[k] = self.map_document(
                                v["data"],
                                v["_nest_collection"],
                                v["_nest_database"],
                                force_nested=True,
                            )
                    elif isinstance(v, list):
                        for i, li in enumerate(v):
                            if isinstance(li, dict) and "_nest_collection" in li:
                                data[k][i] = self.map_document(
                                    li["data"],
                                    li["_nest_collection"],
                                    li["_nest_database"],
                                    force_nested=True,
                                )

            _id = data.pop("_id", None)
            if _id:
                data["_mongodb_id"] = _id

            for field in dataclasses.fields(cls["constructor"]):
                if field.init is False:
                    data.pop(field.name, None)

            return cls["constructor"](**data)

        def mongoclass(
                self,
                collection: str | None = None,
                database: str | pymongo.database.Database | None = None,
                insert_on_init: bool = False,
                nested: bool = False,
        ) -> Callable:
            """A decorator used to map a dataclass onto a collection.

            In other words, it converts the dataclass onto a mongoclass.

            Arguments:
                collection:
                    The collection the class must map to. Defaults to the name of the class but lowered.
                database : Union[str, Database]
                    The database to use. Defaults to the default database.
                insert_on_init:
                    Whether to automatically insert a mongoclass into mongodb whenever a mongoclass instance is created.
                    Defaults to True. This is the equivalent of passing `_insert=True` every time you
                    create a mongoclass instance.
                    This can also be overwritten by setting `_insert=False`
                nested:
                    Whether this mongoclass has other mongoclasses inside it. Nesting is not automatically
                    determined for performance purposes. Defaults to False.
            """
            db = self.__choose_database(database)

            def wrapper(cls):
                collection_name = collection or cls.__name__.lower()

                # noinspection PyMethodParameters,PyShadowingNames
                @functools.wraps(cls, updated=())
                class Inner(cls):
                    COLLECTION_NAME = collection_name
                    DATABASE_NAME = db.name

                    # pylint:disable=no-self-argument
                    def __init__(this, *args, **kwargs) -> None:
                        # MongoDB Attributes
                        this._mongodb_collection = collection_name
                        this._mongodb_client: MongoClient | (MongitaClientDisk | MongitaClientMemory) = db.client
                        this._mongodb_db: pymongo.database.Database | mongita.database.Database = db
                        this._mongodb_id = kwargs.pop("_mongodb_id", None)

                        _insert = kwargs.pop("_insert", insert_on_init)
                        super().__init__(*args, **kwargs)

                        # Perform inserting if needed
                        if _insert:
                            this.insert()

                    def collection(this) -> pymongo.collection.Collection:
                        """Returns collection object."""
                        return this.mongodb_db[this._mongodb_collection]

                    def createIndex(self, field: str) -> str:  # noqa: N802
                        """Creates an unique index.

                        Examples:
                            >>> # noinspection PyUnresolvedReferences
                            >>> user.createIndex("email")  # doctest: +SKIP
                            'email_1

                        Args:
                            field (str): the field to create index

                        Returns:
                            {field}_1
                        """
                        return self.collection().create_index(field, unique=True)

                    def distinct(this, field: str, query: dict | None = None) -> list[str | (int | (dict | list))]:
                        """Returns distinct values.

                        Examples:
                            >>> # noinspection PyUnresolvedReferences
                            >>> user.distinct("email")  # doctest: +SKIP
                            ['john@gmail.com']

                        Args:
                            field (str): the field to get distinct values
                            query (dict): the query to filter
                        """
                        return this.collection().distinct(field, query)

                    def find(self, *fargs, **fkwargs) -> Cursor:
                        """Returns find.

                        Examples:
                            >>> # noinspection PyUnresolvedReferences
                            >>> user.find({}, {"email": 1, "_id": 0})  # doctest: +SKIP
                            <pymongo.cursor.Cursor object at 0x1102d7cd0>
                            >>> # noinspection PyUnresolvedReferences
                            >>> list(user.find({}, {"email": 1, "_id": 0}))  # doctest: +SKIP
                            [{'email': 'john@gmail.com'}]

                        Args:
                            *fargs: args to pass to find
                            **fkwargs: kwargs to pass to find
                        """
                        return self.collection().find(*fargs, **fkwargs)

                    def getIndexes(this) -> CommandCursor[MutableMapping[str, Any]]:  # noqa: N802
                        """Returns indexes.

                        Examples:
                            >>> # noinspection PyUnresolvedReferences
                            >>> user.getIndexes()  # doctest: +SKIP
                            [SON([('v', 2), ('key', SON([('_id', 1)])), ('name', '_id_')]),\
 SON([('v', 2), ('key', SON([('email', 1)])), ('name', 'email_1'), ('unique', True)])]

                        """
                        return this.collection().list_indexes()

                    def has(this) -> bool:
                        """Returns True if this object is inserted.

                        Examples:
                            >>> # noinspection PyUnresolvedReferences
                            >>> user = User("John Howard") # doctest: +SKIP
                            >>> user.has()  # doctest: +SKIP
                            False
                            >>> user.insert()  # doctest: +SKIP
                            >>> user.has()  # doctest: +SKIP
                            True
                        """
                        return bool(this.one())

                    def id(this) -> ObjectId:  # noqa: A003
                        """Returns the ObjectId.

                        Examples:
                            >>> # noinspection PyUnresolvedReferences
                            >>> user = User("John Howard") # doctest: +SKIP
                            >>> user.id()  # doctest: +SKIP
                            >>> user.insert()  # doctest: +SKIP
                            >>> user.id()  # doctest: +SKIP
                            '64f48d7f12247320a50db63b'
                        """
                        return this._mongodb_id

                    def indexValue(this) -> int | str | dict | list | None:  # noqa: N802
                        """Returns the unique index value of the instance.

                        Examples:
                            >>> # noinspection PyUnresolvedReferences
                            >>> user.indexValue()  # doctest: +SKIP
                            "john@gmail.com"
                        """
                        if one := this.one():
                            return one.get(this.indexName())
                        return None

                    def indexName(this) -> str | None:  # noqa: N802
                        """Returns the unique index name.

                        Examples:
                            >>> # noinspection PyUnresolvedReferences
                            >>> user.indexName()  # doctest: +SKIP # noqa: N802
                            "email"
                        """
                        for i in this.getIndexes():
                            if i.get("unique"):
                                return next(iter(i.get("key").keys()))
                        return None

                    @property
                    def mongodb_client(self) -> MongoClient | (MongitaClientDisk | MongitaClientMemory):
                        """Mongo db client."""
                        return self._mongodb_client

                    # noinspection PyPropertyDefinition
                    @property
                    def mongodb_db(this) -> pymongo.database.Database | mongita.database.Database:
                        """Mongo db instance adds test if running in test."""
                        return this._mongodb_db

                    # noinspection PyPropertyDefinition
                    @mongodb_db.setter
                    def mongodb_db(this, value: str | pymongo.database.Database | None):
                        """Mongo db instance adds -test if running is test."""
                        if isinstance(value, (pymongo.database.Database | mongita.database.Database)):
                            this._mongodb_db = value
                        elif is_testing():
                            this._mongodb_db = this._mongodb_client[
                                value if MONGOCLASS_TEST_SUFFIX in value else f"{value}{MONGOCLASS_TEST_SUFFIX}"]
                        else:
                            this._mongodb_db = this._mongodb_client[
                                value.replace(MONGOCLASS_TEST_SUFFIX, "")]

                    def one(self) -> dict | None:
                        """Find is this object is inserted.

                        Examples:
                            >>> # noinspection PyUnresolvedReferences
                            >>> user = User("John Howard", "john@gmail.com", 8771, "PH") # doctest: +SKIP
                            >>> user.one()  # doctest: +SKIP
                            >>> user.insert()  # doctest: +SKIP
                            >>> user.one()  # doctest: +SKIP
                            {'_id': ObjectId('64f4873f27418cd06ed11833'), 'name': 'John Howard',\
 'email': 'john@gmail.com', 'phone': 8771, 'country': 'PH'}

                        """
                        return self.collection().find_one(self.as_json())

                    def rm(self) -> pymongo.results.DeleteResult | mongita.results.DeleteResult:
                        """Delete instance/one.

                        Examples:
                            >>> # noinspection PyUnresolvedReferences
                            >>> user = User("John Howard", "john@gmail.com", 8771, "PH") # doctest: +SKIP
                            >>> user.one()  # doctest: +SKIP
                            >>> user.insert()  # doctest: +SKIP
                            >>> rv = user.rm()  # doctest: +SKIP
                            >>> rv  # doctest: +SKIP
                            <pymongo.results.DeleteResult object at 0x110208580>
                            >>> rv.deleted_count
                            1
                        """
                        return self.collection().delete_one({"_id": self._mongodb_id})

                    def insert(
                            this, *args, **kwargs
                    ) -> dict | object:
                        """Insert this mongoclass as a document in the collection.

                        In case DuplicateKeyError then it will save to update

                        Arguments:
                            *args: Other parameters to be passed onto `Database.insert_one`
                            **kwargs: Other parameters to be passed onto `Database.insert_one`

                        Returns:
                            `InsertOneResult`
                        """
                        try:
                            if query := this.mongodb_db[this._mongodb_collection].find_one(this.as_json()):
                                this._mongodb_id = query["_id"]
                                return query
                            res = this.mongodb_db[this._mongodb_collection].insert_one(
                                this.as_json(), *args, **kwargs
                            )
                            this._mongodb_id = res.inserted_id
                            return this.mongodb_db[this._mongodb_collection].find_one({"_id": this._mongodb_id})
                        except (DuplicateKeyError, mongita.errors.DuplicateKeyError):
                            data = this.as_json()
                            result, new = this.update({"$set": data}, *args, return_new=True, **kwargs)
                            return new

                    def update(
                            this, operation: dict, *args, **kwargs
                    ) -> tuple[
                        UpdateResult | mongita.results.UpdateResult,
                        object,
                    ]:
                        """Update this mongoclass document in the collection..

                        Examples:
                            >>> # noinspection PyUnresolvedReferences
                            >>> john = User("John Dee", "johndee@gmail.com", 5821)  # doctest: +SKIP
                            >>> john.insert()  # doctest: +SKIP
                            >>> # Let's change john's country to UK
                            >>> update_result, new_john = john.update( {"$set": {"country": "UK"}}, \
                                return_new=True)  # doctest: +SKIP

                        Arguments:
                        operation: The operation to be made.
                        return_new:
                            Whether to return a brand new class containing the updated data. Defaults to False. If
                            this is false, the same object is returned.
                        *args: Other parameters to be passed onto `Collection.update_one`
                        **kwargs: Other parameters to be passed onto `Collection.update_one`


                        Returns:
                            `Tuple[UpdateResult, Optional[object]]`
                        """
                        return_new = kwargs.pop("return_new", True)

                        res = this.mongodb_db[this._mongodb_collection].update_one(
                            {"_id": this._mongodb_id}, operation, *args, **kwargs
                        )
                        return_value = this
                        if return_new:
                            _id = this._mongodb_id or res.upserted_id
                            if _id:
                                return_value = self.find_class(
                                    this._mongodb_collection,
                                    {"_id": _id},
                                    database=this.mongodb_db,
                                )

                        return res, return_value

                    def save(
                            this, *args, **kwargs
                    ) -> tuple[dict | object, Inner] | tuple[UpdateResult, object]:
                        """Update this mongoclass document in the collection with the current state of the object.

                        If this document doesn't exist yet, it will just call `.insert()`

                        Here's a comparison of `.save()` and `.update()` doing the same exact thing.

                        Examples:
                            >>> # Using .update()
                            >>> # noinspection PyUnresolvedReferences
                            >>> user.update({"$set": {"name": "Robert Downey"}})
                            >>>
                            >>> # Using .save()
                            >>> # noinspection PyUnresolvedReferences
                            >>> user.name = "Robert Downey"
                            >>> # noinspection PyUnresolvedReferences
                            >>> user.save()

                        Under the hood, this is just calling .update() using the set operator.

                        Arguments:
                        *args: To be passed onto `.update()`
                        **kwargs: To be passed onto `.update()`


                        Returns:
                            `Tuple[Union[UpdateResult, InsertResult], object]`
                        """
                        if not this._mongodb_id:
                            return this.insert(), this

                        data = this.as_json()
                        return this.update({"$set": data}, *args, **kwargs)

                    def delete(
                            this, *args, **kwargs
                    ) -> pymongo.results.DeleteResult | mongita.results.DeleteResult:
                        """Delete this mongoclass in the collection.

                        Arguments:
                            *args: To be passed onto `Collection.delete_one`
                            **kwargs: To be passed onto `Collection.delete_one`


                        Returns:
                            `DeleteResult`
                        """
                        return this.mongodb_db[this._mongodb_collection].delete_one(
                            {"_id": this._mongodb_id}, *args, **kwargs
                        )

                    @staticmethod
                    def count_documents(*args, **kwargs) -> int:
                        """Count the number of documents in this collection.

                        Examples:
                            >>> # noinspection PyUnresolvedReferences
                            >>> user.count_documents({})  # doctest: +SKIP
                            1

                        Arguments:
                        *args: To be passed onto `Collection.count_documents`
                        **kwargs: To be passed onto `Collection.count_documents`

                        Returns:
                            `int`
                        """
                        return db[collection_name].count_documents(*args, **kwargs)

                    @staticmethod
                    def find_class(
                            *args,
                            database: str | (pymongo.database.Database | mongita.database.Database) | None = None,
                            **kwargs,
                    ) -> object | None:
                        """Find a single document from this class and convert it onto a mongoclass.

                        That maps to the collection of the document.

                        Examples:
                            >>> # noinspection PyUnresolvedReferences
                            >>> user = User("John Howard", "john@gmail.com", 8771, "PH") # doctest: +SKIP
                            >>> user.find_class()  # doctest: +SKIP
                            >>> user.insert()  # doctest: +SKIP
                            >>> user.find_class()  # doctest: +SKIP
                            create_class.<locals>.User(name='John Howard',\
email='john@gmail.com', phone=8771, country='PH')


                        Arguments:
                            *args: Arguments to pass onto `find_one`.
                            database: The database to use. Defaults to the default database.
                            **kwargs: Keyword arguments to pass onto `find_one`.

                        Returns:
                            `Optional[object]`: The mongoclass containing the document's data if it exists.
                        """
                        return self.find_class(
                            collection_name, *args, database, **kwargs
                        )

                    @staticmethod
                    def aggregate(
                            *args,
                            database: str | (pymongo.database.Database | mongita.database.Database) | None = None,
                            **kwargs,
                    ) -> Cursor:
                        db = self.choose_database(database)
                        query = db[collection_name].aggregate(*args, **kwargs)

                        return Cursor(
                            query,
                            self.map_document,
                            collection_name,
                            db.name,
                            self._engine_used,
                        )

                    @staticmethod
                    def paginate(
                            *args,
                            database: str | (pymongo.database.Database | mongita.database.Database) | None = None,
                            pre_call=None,
                            page: int,
                            size: int,
                            **kwargs,
                    ) -> Cursor:
                        skip = (page - 1) * size

                        cursor = self.find_classes(
                            collection_name, *args, database, **kwargs
                        )

                        if pre_call:
                            cursor = pre_call(cursor)

                        return cursor.skip(skip).limit(size)

                    @staticmethod
                    def find_classes(
                            *args,
                            database: str | (pymongo.database.Database | mongita.database.Database) | None = None,
                            **kwargs,
                    ) -> Cursor:
                        """Find multiple document from this class s and return a `Cursor` that you can iterate over.

                         That contains the documents as a mongoclass.

                        Examples:
                            >>> # noinspection PyUnresolvedReferences
                            >>> user = User("John Howard", "john@gmail.com", 8771, "PH") # doctest: +SKIP
                            >>> user.find_classes()  # doctest: +SKIP
                            >>> user.insert()  # doctest: +SKIP
                            >>> user.find_classes()  # doctest: +SKIP
                            <mongoclass.cursor.Cursor object at 0x1102d7cd0>


                        Arguments:
                            *args: Arguments to pass onto `find`.
                            database: The database to use. Defaults to the default database.
                            **kwargs:  Keyword arguments to pass onto `find`.

                        Returns:
                            `Cursor`: A cursor similar to pymongo that you can iterate over to get the results.
                        """
                        return self.find_classes(
                            collection_name, *args, database, **kwargs
                        )

                    def as_json(this, perform_nesting: bool = nested) -> dict:
                        """Convert this mongoclass into a json serializable object.

                        This will pop mongodb and mongoclass reserved attributes such as _mongodb_id, _
                        mongodb_collection, etc.
                        """
                        x = copy.copy(this.__dict__)
                        x.pop("_mongodb_collection", None)
                        x.pop("_mongodb_client", None)
                        x.pop("_mongodb_db", None)
                        x.pop("_mongodb_id", None)
                        x.pop("_id", None)

                        def create_nest_data(v, as_json):
                            return {
                                "data": as_json(perform_nesting),
                                "_nest_collection": v._mongodb_collection,
                                "_nest_database": v.mongodb_db.name,
                            }

                        def get_as_json(v):
                            with contextlib.suppress(AttributeError):
                                return v.as_json

                        if perform_nesting:
                            for k, v in copy.copy(x).items():
                                if dataclasses.is_dataclass(v):
                                    as_json_method = get_as_json(v)
                                    if as_json_method:
                                        x[k] = create_nest_data(v, as_json_method)

                                elif isinstance(v, list):
                                    c = v.copy()
                                    for i, li in enumerate(c):
                                        if dataclasses.is_dataclass(li):
                                            as_json_method = get_as_json(li)
                                            if as_json_method:
                                                c[i] = create_nest_data(
                                                    li, as_json_method
                                                )

                                    x[k] = c

                        return x

                if db.name not in self.mapping:
                    self.mapping[db.name] = {}

                self.mapping[db.name][collection_name] = {
                    "constructor": Inner,
                    "nested": nested,
                }
                return Inner

            return wrapper

        def find_class(
                self,
                collection: str,
                *args,
                database: str | (pymongo.database.Database | mongita.database.Database) | None = None,
                **kwargs,
        ) -> object | None:
            """Find a single document and convert it onto a mongoclass that maps to the collection of the document.

            Arguments:
                collection: The collection to use.
                *args: Arguments to pass onto `find_one`.
                database: The database to use. Defaults to the default database.
                **kwargs: Keyword arguments to pass onto `find_one`.

            Returns:
                `Optional[object]`: The mongoclass containing the document's data if it exists.
            """
            db = self.__choose_database(database)
            query = db[collection].find_one(*args, **kwargs)
            if not query:
                return None
            return self.map_document(query, collection, db.name)

        find_one = find_class

        def find_classes(
                self,
                collection: str,
                *args,
                database: str | (pymongo.database.Database | mongita.database.Database) | None = None,
                **kwargs,
        ) -> Cursor:
            """Find multiple documents and return a `Cursor` that you can iterate over that contains the documents.

            As a mongoclass.

            Arguments:
                collection: The collection to use.
                *args: Arguments to pass onto `find`.
                database: The database to use. Defaults to the default database.
                **kwargs: Keyword arguments to pass onto `find`.

            Returns:
                `Cursor`: A cursor similar to pymongo that you can iterate over to get the results.
            """
            db = self.__choose_database(database)
            query = db[collection].find(*args, **kwargs)
            return Cursor(
                query, self.map_document, collection, db.name, self._engine_used
            )

        # noinspection PyMethodMayBeStatic
        def insert_classes(
                self,
                mongoclasses: object | (pymongo.collection.Collection | list[object]),
                *args,
                **kwargs
        ) -> pymongo.results.InsertOneResult | pymongo.results.InsertManyResult | list[pymongo.results.InsertOneResult]:
            """Insert a mongoclass or a list of mongoclasses into its respective collection and database.

            This method can accept mongoclasses with different collections and different databases as
            long as `insert_one` is `True`.

            Examples:
                >>> # noinspection PyUnresolvedReferences
                >>> users = [User("John Dee", "johndee@gmail.com", 100), \
                User("Michael Reeves", "michaelreeves@gmail.com", 42069) ]   # docstring: +SKIP
                >>> # noinspection PyUnresolvedReferences
                >>> client.insert_classes(users)  # docstring: +SKIP

            Notes:
                If you're inserting multiple mongoclasses with `insert_one=False` and `ordered=False`, the provided
                mongoclasses will be mutated by setting a `_mongodb_id` attribute with the id coming from
                `InsertManyResult` after this method executes.

            Arguments:
            mongoclasses: A list of mongoclasses or a single mongoclass. When inserting a single mongoclass,
                you can just do `mongoclass.insert()`
            insert_one: Whether to call `mongoclass.insert()` on each mongoclass. Defaults to False.
                False means it would use `Collection.insert_many` to insert all the documents at once.
            *args: To be passed onto `Collection.insert_many` or `mongoclass.insert()`
            **kwargs: To be passed onto `Collection.insert_many` or `mongoclass.insert()`

            Returns:
            `Union[InsertOneResult, InsertManyResult, List[InsertOneResult]]`:
                - A `InsertOneResult` if the provided `mongoclasses` parameters is just a single mongoclass.
                - A `InsertManyResult` if the provided `mongoclasses` parameter is a list of mongoclasses
            """
            insert_one = kwargs.pop("insert_one", False)
            if not isinstance(mongoclasses, list):
                return mongoclasses.insert(*args, **kwargs)

            if insert_one:
                results = []
                for mongoclass in mongoclasses:
                    results.append(mongoclass.insert(*args, **kwargs))
                return results

            collection, database = (
                mongoclasses[0]._mongodb_collection,
                mongoclasses[0].mongodb_db,
            )
            insert_result = database[collection].insert_many(
                [x.as_json() for x in mongoclasses], *args, **kwargs
            )
            if kwargs.get("ordered"):
                return insert_result

            for mongoclass, inserted in zip(mongoclasses, insert_result.inserted_ids, strict=True):
                mongoclass._mongodb_id = inserted

            return insert_result

        insert_many = insert_classes

    return MongoClassClientClass(*args, **kwargs)


def MongoClassClient(  # noqa: N802
        *args,
        **kwargs
) -> SupportsMongoClassClient | (MongoClient | pymongo.database.Database):
    """Mongo Class CLient.

    Examples:
        >>> from mongodata import MongoClassClient
        >>> MongoClassClient("test", "mongodb://localhost:27017")
        MongoClient(host=['localhost:27017'], document_class=dict, tz_aware=False, connect=True)

    """
    return client_constructor("pymongo", *args, **kwargs)


warnings.filterwarnings(action="ignore", message="unclosed", category=ResourceWarning)

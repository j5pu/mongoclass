from __future__ import annotations
import contextlib
import copy
import dataclasses
import functools
import inspect
import json
import os
import warnings
from typing import Any
from typing import Callable
from typing import List
from typing import MutableMapping
from typing import Optional
from typing import Protocol
from typing import Union

import furl
import mongita.database
import mongita.results
import pymongo.collection
import pymongo.database
import pymongo.results
import requests
import rich.pretty
import rich.traceback
from bson import ObjectId
from furl.common import absent as _absent
from mongita import MongitaClientDisk
from mongita import MongitaClientMemory
from mongita.results import UpdateResult
from pymongo import MongoClient
from pymongo.command_cursor import CommandCursor
from pymongo.errors import DuplicateKeyError
from pymongo.results import UpdateResult
from requests.auth import HTTPDigestAuth

from mongoclass.cursor import Cursor

__all__ = (
    "CONSOLE",
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

# ATLAS = "mongodb+srv://j5pu:1Zaragoza1@cluster0.xxjqsmg.mongodb.net"
# CLIENT = pymongo.MongoClient(f"{ATLAS}/?retryWrites=true&w=majority")
CONSOLE = rich.console.Console(force_interactive=True, color_system='256')
# MONGO = mongoclass.MongoClassClient("pdf", f"{ATLAS}/?retryWrites=true&w=majority")


rich.pretty.install(CONSOLE, expand_all=True)
rich.traceback.install(show_locals=True)


def atlas_api(url, query: dict = None, user: str = None, password: str = None, payload=None) -> Optional[dict]:
    """
    Atlas API

    Examples:
        >>> from mongoclass.client import atlas_api
        >>>
        >>> atlas_api("groups")  # doctest: +ELLIPSIS
        {'links': [{'href': '...', 'rel': 'self'}], 'results': [{'clusterCount': 1, 'created': '2023-09-02T08:30:14Z',\
 'id': '...', 'links': [{'href': '...', 'rel': 'self'}], 'name': 'pdf', 'orgId': '...'}], 'totalCount': ...}

    Args:
        url: url
        query:
        user: user
        password: password
        payload: payload
    """
    user = user if user else os.environ.get("ATLAS_PUBLIC_KEY_MNOPI")
    password = password if password else os.environ.get("ATLAS_PRIVATE_KEY_MNOPI")
    if user is None or password is None:
        raise RuntimeError(f"user and password must be set or pass as arguments: {user=}, {password=}")

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


def atlas_add_ip(project: str) -> Optional[dict]:
    """
    Add ip to project

    Examples:
        >>> from mongoclass.client import atlas_add_ip
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
        raise RuntimeError(f"{project=} not found")

    payload = json.dumps([{"cidrBlock": f"{requests.get('https://checkip.amazonaws.com').text.strip()}/32"}])

    response = atlas_api(f"groups/{group_id}/accessList", payload=payload)

    return response


def client_mongoclass(
        atlas: bool = True,
        db: str = "main",
        host: str = _absent,
        password: str = _absent,
        port: Union[str, int] = _absent,
        query: dict = _absent,
        scheme: dict = _absent,
        username: str = _absent,
) -> Union[SupportsMongoClassClient, MongoClient, pymongo.database.Database]:
    """
    Returns a MongoClient

    Examples:
        >>> from mongoclass.client import client_mongoclass
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
        port: Union[str, int] = _absent,
        query: dict = _absent,
        scheme: dict = _absent,
        username: str = _absent,
) -> MongoClient:
    """
    Returns a MongoClient

    Examples:
        >>> from mongoclass.client import client_pymongo
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
    """
    True if env var `MONGOCLASS_PRODUCTION` is None or any of pytest, docrunner, unittest, PyCharm in callers filenames.

    Examples:
        >>> from mongoclass.client import is_testing
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
        port: Union[str, int] = _absent,
        query: dict = _absent,
        scheme: dict = _absent,
        username: str = _absent,
) -> str:
    """
    Returns atlas url for connection

    Examples:
        >>> from mongoclass.client import mongo_url
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
    """
    A decorator that will run the function if TESTING is False.

    Examples:
        >>> from mongoclass.client import is_testing
        >>> from mongoclass.client import run_if_production
        >>> from mongoclass.client import run_in_production
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
            return
        return func(*args, **kwargs)

    return wrapper


@contextlib.contextmanager
def run_in_production():
    """
    A context manager that will set TESTING to False.

    Examples:
        >>> with run_in_production():
        ...     is_testing()
        False
    """
    os.environ["MONGOCLASS_PRODUCTION"] = "1"
    yield
    del os.environ["MONGOCLASS_PRODUCTION"]


class SupportsMongoClass(Protocol):
    COLLECTION_NAME: str
    DATABASE_NAME: str
    _mongodb_collection: str
    _mongodb_db: Union[pymongo.database.Database, mongita.database.Database]
    _mongodb_id: ObjectId

    @property
    def collection(self) -> pymongo.collection.Collection:
        return ...

    def createIndex(self, field: str): ...

    def distinct(self, field: str, query: dict) -> List[Union[str, int, dict, list]]: ...

    def find(self, *args, **kwargs) -> Cursor: ...

    def getIndexes(self) -> CommandCursor[MutableMapping[str, Any]]: ...

    def has(self) -> bool: ...

    @property
    def id(self) -> ObjectId:
        return ...

    @property
    def indexName(self) -> Optional[str]:
        return ...

    @property
    def indexValue(self) -> Union[int, str, dict, list]:
        return ...

    def one(self) -> Optional[dict]: ...

    def rm(self) -> Union[
        pymongo.results.DeleteResult, mongita.results.DeleteResult
    ]: ...

    def insert(self, *args, **kwargs) -> dict: ...

    def update(self, operation: dict, *args, **kwargs) -> tuple[
        Union[pymongo.results.UpdateResult, mongita.results.UpdateResult], object,
    ]: ...

    def save(self, *args, **kwargs) -> tuple[
        Union[
            pymongo.results.UpdateResult,
            pymongo.results.InsertOneResult,
            mongita.results.InsertOneResult,
            mongita.results.UpdateResult,
        ],
        object,
    ]: ...

    def delete(self, *args, **kwargs) -> Union[
        pymongo.results.DeleteResult, mongita.results.DeleteResult
    ]: ...

    @staticmethod
    def count_documents(*args, **kwargs) -> int: ...

    @staticmethod
    def find_class(*args, database: Optional[
        Union[
            str,
            pymongo.database.Database,
            mongita.database.Database,
        ]
    ] = ...,
                   **kwargs,
                   ) -> Optional[object]: ...

    find_one = find_class

    @staticmethod
    def aggregate(
            *args,
            database: Optional[
                Union[
                    str,
                    pymongo.database.Database,
                    mongita.database.Database,
                ]
            ] = ...,
            **kwargs,
    ) -> Cursor: ...

    @staticmethod
    def paginate(
            *args,
            database: Optional[
                Union[
                    str,
                    pymongo.database.Database,
                    mongita.database.Database,
                ]
            ] = ...,
            pre_call: Optional[Callable] = ...,
            page: int,
            size: int,
            **kwargs,
    ) -> Cursor: ...

    @staticmethod
    def find_classes(
            *args,
            database: Optional[
                Union[
                    str,
                    pymongo.database.Database,
                    mongita.database.Database,
                ]
            ] = ...,
            **kwargs,
    ) -> Cursor: ...

    def as_json(self, perform_nesting: bool = ...) -> dict: ...

    def insert_classes(
            self, mongoclasses: Union[object, List[object]], *args, **kwargs
    ) -> Union[
        pymongo.results.InsertOneResult,
        pymongo.results.InsertManyResult,
        List[pymongo.results.InsertOneResult],
    ]: ...

    insert_many = insert_classes


class SupportsMongoClassClient(Protocol):
    mapping: dict = ...
    default_database: pymongo.database.Database

    def choose_database(self, database: Optional[
        Union[
            str,
            pymongo.database.Database,
            mongita.database.Database,
        ]
    ] = ...) -> Union[pymongo.database.Database, mongita.database.Database]: ...

    def get_db(self, database: str) -> Union[pymongo.database.Database, mongita.database.Database]: ...

    def map_document(self, data: dict, collection: str, database: str, force_nested: bool = ...) -> object: ...

    def mongoclass(
            self,
            collection: Optional[str] = ...,
            database: Optional[Union[str, pymongo.database.Database]] = ...,
            insert_on_init: bool = ...,
            nested: bool = ...,
    ) -> Union[Callable, SupportsMongoClass]: ...

    def find_class(
            self,
            collection: str,
            *args,
            database: Optional[
                Union[
                    str,
                    pymongo.database.Database,
                    mongita.database.Database,
                ]
            ] = ...,
            **kwargs,
    ) -> Optional[object]: ...

    def find_classes(self, collection: str, *args, database: Optional[
        Union[
            str,
            pymongo.database.Database,
            mongita.database.Database,
        ]
    ] = ..., **kwargs,
                     ) -> Cursor: ...

    def insert_classes(
            self, mongoclasses: Union[object, pymongo.collection.Collection, List[object]], *args, **kwargs
    ) -> Union[
        pymongo.results.InsertOneResult,
        pymongo.results.InsertManyResult,
        List[pymongo.results.InsertOneResult],
    ]: ...

    insert_many = insert_classes


# noinspection PyPep8Naming
def client_constructor(engine: str, *args, **kwargs) -> Union[
    SupportsMongoClassClient, MongoClient, pymongo.database.Database
]:
    if engine == "pymongo":
        Engine = MongoClient
    elif engine == "mongita_disk":
        Engine = MongitaClientDisk
    elif engine == "mongita_memory":
        Engine = MongitaClientMemory
    else:
        raise ValueError(f"Invalid engine '{engine}'")

    # noinspection PyShadowingNames
    class MongoClassClientClass(Engine):  # type: ignore
        """
        Parameters
        ----------
        `default_db_name` : str
            The name of the default database.
        `*args, **kwargs` :
            To be passed onto `MongoClient()` or `MongitaClientDisk()`
        """

        def __init__(self, default_db_name: str = "main", *args, **kwargs) -> None:
            super().__init__(*args, **kwargs)
            self.mapping = {}

            if is_testing():
                default_db_name = f"{default_db_name}-test"

            self.default_database: Union[
                pymongo.database.Database, mongita.database.Database
            ] = self[default_db_name]

            # Determine engine being used
            self._engine_used = engine

        def __choose_database(
                self,
                database: Optional[
                    Union[str, pymongo.database.Database, mongita.database.Database]
                ] = None,
        ) -> Union[pymongo.database.Database, mongita.database.Database]:
            if database is None:
                return self.default_database
            if isinstance(
                database, (pymongo.database.Database, mongita.database.Database)
            ):
                return database
            return self[database]

        choose_database = __choose_database

        def get_db(
                self, database: str
        ) -> Union[pymongo.database.Database, mongita.database.Database]:
            """
            Get a database. Equivalent to `client["database"]`. This method exists simply because type hinting seems
            to be broken, nothing more.

            Parameters
            ----------
            `database` : str
                The name of the database.

            Returns
            -------
            `Union[pymongo.database.Database, mongita.database.Database]` :
                The `Database` object of the underlying engine.
            """

            return self[database]

        def map_document(
                self, data: dict, collection: str, database: str, force_nested: bool = False
        ) -> object:
            """
            Map a raw document into a mongoclass.

            Parameters
            ----------
            `data` : dict
                The raw document coming from a collection.
            `collection` : str
                The collection this maps to. The collection then maps onto an actual mongoclass object.
            `database` : str
                The database the raw document belongs to.
            `force_nested` : bool
                Forcefully tell mongoclass that this document is a nested document and it contains other mongoclasses
                inside it. Defaults to False. Usually this parameter is only set in a recursive manner.
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
                collection: Optional[str] = None,
                database: Optional[Union[str, pymongo.database.Database]] = None,
                insert_on_init: bool = False,
                nested: bool = False,
        ) -> Callable:
            """
            A decorator used to map a dataclass onto a collection.
            In other words, it converts the dataclass onto a mongoclass.

            Parameters
            ----------
            `collection` : str
                The collection the class must map to. Defaults to the name of the class but lowered.
            `database` : Union[str, Database]
                The database to use. Defaults to the default database.
            `insert_on_init` : bool
                Whether to automatically insert a mongoclass into mongodb whenever a mongoclass instance is created.
                Defaults to True. This is the equivalent of passing `_insert=True` every time you create a mongoclass
                instance.
                This can also be overwritten by setting `_insert=False`
            `nested` : bool
                Whether this mongoclass has other mongoclasses inside it. Nesting is not automatically determined for
                performance purposes. Defaults to False.

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
                        this._mongodb_db = db
                        this._mongodb_id = kwargs.pop("_mongodb_id", None)

                        _insert = kwargs.pop("_insert", insert_on_init)
                        super().__init__(*args, **kwargs)

                        # Perform inserting if needed
                        if _insert:
                            this.insert()

                    def collection(this) -> pymongo.collection.Collection:
                        """returns collection object"""
                        return this._mongodb_db[this._mongodb_collection]

                    def createIndex(self, field: str) -> str:
                        """creates an unique index

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

                    def distinct(this, field: str, query: dict = None) -> List[Union[str, int, dict, list]]:
                        """
                        returns distinct values

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
                        """
                        returns find

                        Examples:
                            >>> # noinspection PyUnresolvedReferences
                            >>> user.find({}, {"email": 1, "_id": 0})  # doctest: +SKIP
                            <pymongo.cursor.Cursor object at 0x1102d7cd0>
                            >>> # noinspection PyUnresolvedReferences
                            >>> list(user.find({}, {"email": 1, "_id": 0}))  # doctest: +SKIP
                            [{'email': 'john@gmail.com'}]

                        Args:
                            *fargs:
                            **fkwargs:
                        """
                        return self.collection().find(*fargs, **fkwargs)

                    def getIndexes(this) -> CommandCursor[MutableMapping[str, Any]]:
                        """
                        returns indexes

                        Examples:
                            >>> # noinspection PyUnresolvedReferences
                            >>> user.getIndexes()  # doctest: +SKIP
                            [SON([('v', 2), ('key', SON([('_id', 1)])), ('name', '_id_')]),\
 SON([('v', 2), ('key', SON([('email', 1)])), ('name', 'email_1'), ('unique', True)])]

                        """
                        return this.collection().list_indexes()

                    def has(this) -> bool:
                        """
                        Returns True if this object is inserted

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

                    def id(this) -> ObjectId:
                        """
                        Returns the ObjectId

                        Examples:
                            >>> # noinspection PyUnresolvedReferences
                            >>> user = User("John Howard") # doctest: +SKIP
                            >>> user.id()  # doctest: +SKIP
                            >>> user.insert()  # doctest: +SKIP
                            >>> user.id()  # doctest: +SKIP
                            '64f48d7f12247320a50db63b'


                        """
                        return this._mongodb_id

                    def indexValue(this) -> Union[int, str, dict, list]:
                        """
                        Returns the unique index value of the instance

                        Examples:
                            >>> # noinspection PyUnresolvedReferences
                            >>> user.indexValue()  # doctest: +SKIP
                            "john@gmail.com"

                        """
                        if one := this.one():
                            return one.get(this.indexName())

                    def indexName(this) -> Optional[str]:
                        """
                        Returns the unique index name

                        Examples:
                            >>> # noinspection PyUnresolvedReferences
                            >>> user.indexName()  # doctest: +SKIP
                            "email"

                        """
                        for i in this.getIndexes():
                            if i.get("unique"):
                                return list(i.get("key").keys())[0]

                    def one(self) -> Optional[dict]:
                        """
                        Find is this object is inserted

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

                    def rm(self) -> Union[
                        pymongo.results.DeleteResult, mongita.results.DeleteResult
                    ]:
                        """
                        Delete instance/one
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
                    ) -> Union[dict, object]:
                        """
                        Insert this mongoclass as a document in the collection.

                        In case DuplicateKeyError then it will save to update

                        Parameters
                        ----------
                        `*args, **kwargs` :
                            Other parameters to be passed onto `Database.insert_one`

                        Returns
                        -------
                        `InsertOneResult`
                        """
                        try:
                            if query := this._mongodb_db[this._mongodb_collection].find_one(this.as_json()):
                                this._mongodb_id = query["_id"]
                                return query
                            else:
                                res = this._mongodb_db[this._mongodb_collection].insert_one(
                                    this.as_json(), *args, **kwargs
                                )
                                this._mongodb_id = res.inserted_id
                                return this._mongodb_db[this._mongodb_collection].find_one({"_id": this._mongodb_id})
                        except (DuplicateKeyError, mongita.errors.DuplicateKeyError):
                            data = this.as_json()
                            result, new = this.update({"$set": data}, *args, return_new=True, **kwargs)
                            return new

                    def update(
                            this, operation: dict, *args, **kwargs
                    ) -> tuple[
                        Union[
                            pymongo.results.UpdateResult, mongita.results.UpdateResult
                        ],
                        object,
                    ]:
                        """
                        Update this mongoclass document in the collection.

                        Examples:
                            >>> # noinspection PyUnresolvedReferences
                            >>> john = User("John Dee", "johndee@gmail.com", 5821)  # doctest: +SKIP
                            >>> john.insert()  # doctest: +SKIP
                            >>> # Let's change john's country to UK
                            >>> update_result, new_john = john.update( {"$set": {"country": "UK"}}, \
                                return_new=True)  # doctest: +SKIP                        Parameters
                        ----------
                        `operation` : dict
                            The operation to be made.
                        `return_new` : bool
                            Whether to return a brand new class containing the updated data. Defaults to False. If
                            this is false, the same object is returned.
                        `*args, **kwargs` :
                            Other parameters to be passed onto `Collection.update_one`

                        Returns
                        -------
                        `Tuple[UpdateResult, Optional[object]]`
                        """

                        return_new = kwargs.pop("return_new", True)

                        res = this._mongodb_db[this._mongodb_collection].update_one(
                            {"_id": this._mongodb_id}, operation, *args, **kwargs
                        )
                        return_value = this
                        if return_new:
                            _id = this._mongodb_id or res.upserted_id
                            if _id:
                                return_value = self.find_class(
                                    this._mongodb_collection,
                                    {"_id": _id},
                                    database=this._mongodb_db,
                                )

                        return res, return_value

                    def save(
                            this, *args, **kwargs
                    ) -> Union[tuple[Union[dict, object], Inner], tuple[Union[UpdateResult, UpdateResult], object]]:
                        """
                        Update this mongoclass document in the collection with the current state of the object.

                        If this document doesn't exist yet, it will just call `.insert()`

                        Here's a comparison of `.save()` and `.update()` doing the same exact thing.

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

                        Parameters
                        ----------
                        `*args, **kwargs` :
                            To be passed onto `.update()`

                        Returns
                        -------
                        `Tuple[Union[UpdateResult, InsertResult], object]`
                        """

                        if not this._mongodb_id:
                            return this.insert(), this

                        data = this.as_json()
                        return this.update({"$set": data}, *args, **kwargs)

                    def delete(
                            this, *args, **kwargs
                    ) -> Union[
                        pymongo.results.DeleteResult, mongita.results.DeleteResult
                    ]:
                        """
                        Delete this mongoclass in the collection.

                        Parameters
                        ----------
                        `*args, **kwargs` :
                            To be passed onto `Collection.delete_one`

                        Returns
                        -------
                        `DeleteResult`
                        """

                        return this._mongodb_db[this._mongodb_collection].delete_one(
                            {"_id": this._mongodb_id}, *args, **kwargs
                        )

                    @staticmethod
                    def count_documents(*args, **kwargs) -> int:
                        """
                        Count the number of documents in this collection.

                        Examples:
                            >>> # noinspection PyUnresolvedReferences
                            >>> user.count_documents({})  # doctest: +SKIP
                            1

                        Parameters
                        ----------
                        `*args, **kwargs` :
                            To be passed onto `Collection.count_documents`

                        Returns
                        -------
                        `int`
                        """

                        return db[collection_name].count_documents(*args, **kwargs)

                    @staticmethod
                    def find_class(
                            *args,
                            database: Optional[
                                Union[
                                    str,
                                    pymongo.database.Database,
                                    mongita.database.Database,
                                ]
                            ] = None,
                            **kwargs,
                    ) -> Optional[object]:
                        """
                        Find a single document from this class and convert it onto a mongoclass that maps to the
                        collection of the document.

                        Examples:
                            >>> # noinspection PyUnresolvedReferences
                            >>> user = User("John Howard", "john@gmail.com", 8771, "PH") # doctest: +SKIP
                            >>> user.find_class()  # doctest: +SKIP
                            >>> user.insert()  # doctest: +SKIP
                            >>> user.find_class()  # doctest: +SKIP
                            create_class.<locals>.User(name='John Howard',\
email='john@gmail.com', phone=8771, country='PH')


                        Parameters
                        ----------
                        `*args` :
                            Arguments to pass onto `find_one`.
                        `database` : Union[str, Database]
                            The database to use. Defaults to the default database.
                        `**kwargs` :
                            Keyword arguments to pass onto `find_one`.

                        Returns
                        -------
                        `Optional[object]` :
                            The mongoclass containing the document's data if it exists.
                        """

                        return self.find_class(
                            collection_name, *args, database, **kwargs
                        )

                    @staticmethod
                    def aggregate(
                            *args,
                            database: Optional[
                                Union[
                                    str,
                                    pymongo.database.Database,
                                    mongita.database.Database,
                                ]
                            ] = None,
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
                            database: Optional[
                                Union[
                                    str,
                                    pymongo.database.Database,
                                    mongita.database.Database,
                                ]
                            ] = None,
                            pre_call: Optional[Callable] = None,
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

                        results = cursor.skip(skip).limit(size)

                        return results

                    @staticmethod
                    def find_classes(
                            *args,
                            database: Optional[
                                Union[
                                    str,
                                    pymongo.database.Database,
                                    mongita.database.Database,
                                ]
                            ] = None,
                            **kwargs,
                    ) -> Cursor:
                        """
                        Find multiple document from this class s and return a `Cursor` that you can iterate over that
                        contains the documents as a mongoclass.

                        Examples:
                            >>> # noinspection PyUnresolvedReferences
                            >>> user = User("John Howard", "john@gmail.com", 8771, "PH") # doctest: +SKIP
                            >>> user.find_classes()  # doctest: +SKIP
                            >>> user.insert()  # doctest: +SKIP
                            >>> user.find_classes()  # doctest: +SKIP
                            <mongoclass.cursor.Cursor object at 0x1102d7cd0>


                        Parameters
                        ----------
                        `*args` :
                            Arguments to pass onto `find`.
                        `database` : Union[str, Database]
                            The database to use. Defaults to the default database.
                        `**kwargs` :
                            Keyword arguments to pass onto `find`.

                        Returns
                        -------
                        `Cursor`:
                            A cursor similar to pymongo that you can iterate over to get the results.
                        """

                        return self.find_classes(
                            collection_name, *args, database, **kwargs
                        )

                    def as_json(this, perform_nesting: bool = nested) -> dict:
                        """
                        Convert this mongoclass into a json serializable object. This will pop mongodb and mongoclass
                        reserved attributes such as _mongodb_id, _mongodb_collection, etc.
                        """

                        x = copy.copy(this.__dict__)
                        x.pop("_mongodb_collection", None)
                        x.pop("_mongodb_db", None)
                        x.pop("_mongodb_id", None)
                        x.pop("_id", None)

                        def create_nest_data(v, as_json):
                            return {
                                "data": as_json(perform_nesting),
                                "_nest_collection": v._mongodb_collection,
                                "_nest_database": v._mongodb_db.name,
                            }

                        def get_as_json(v):
                            method = None
                            try:
                                method = getattr(
                                    v,
                                    "as_json",
                                )
                            except AttributeError:
                                pass
                            return method

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
                database: Optional[
                    Union[str, pymongo.database.Database, mongita.database.Database]
                ] = None,
                **kwargs,
        ) -> Optional[object]:
            """
            Find a single document and convert it onto a mongoclass that maps to the collection of the document.

            Parameters
            ----------
            `collection` : str
                The collection to use.
            `*args` :
                Arguments to pass onto `find_one`.
            `database` : Union[str, Database]
                The database to use. Defaults to the default database.
            `**kwargs` :
                Keyword arguments to pass onto `find_one`.

            Returns
            -------
            `Optional[object]` :
                The mongoclass containing the document's data if it exists.
            """

            db = self.__choose_database(database)
            query = db[collection].find_one(*args, **kwargs)
            if not query:
                return
            return self.map_document(query, collection, db.name)

        find_one = find_class

        def find_classes(
                self,
                collection: str,
                *args,
                database: Optional[
                    Union[str, pymongo.database.Database, mongita.database.Database]
                ] = None,
                **kwargs,
        ) -> Cursor:
            """
            Find multiple documents and return a `Cursor` that you can iterate over that contains the documents as a
            mongoclass.

            Parameters
            ----------
            `collection` : str
                The collection to use.
            `*args` :
                Arguments to pass onto `find`.
            `database` : Union[str, Database]
                The database to use. Defaults to the default database.
            `**kwargs` :
                Keyword arguments to pass onto `find`.

            Returns
            -------
            `Cursor`:
                A cursor similar to pymongo that you can iterate over to get the results.
            """

            db = self.__choose_database(database)
            query = db[collection].find(*args, **kwargs)
            cursor = Cursor(
                query, self.map_document, collection, db.name, self._engine_used
            )
            return cursor

        # noinspection PyMethodMayBeStatic
        def insert_classes(
                self, mongoclasses: Union[object, pymongo.collection.Collection, List[object]], *args, **kwargs
        ) -> Union[
            pymongo.results.InsertOneResult,
            pymongo.results.InsertManyResult,
            List[pymongo.results.InsertOneResult],
        ]:
            """
            Insert a mongoclass or a list of mongoclasses into its respective collection and database. This method
            can accept mongoclasses with different collections and different databases as long as `insert_one` is
            `True`.

            Examples:
                >>> # noinspection PyUnresolvedReferences
                >>> users = [User("John Dee", "johndee@gmail.com", 100), \
                User("Michael Reeves", "michaelreeves@gmail.com", 42069) ]   # docstring: +SKIP
                >>> # noinspection PyUnresolvedReferences
                >>> client.insert_classes(users)  # docstring: +SKIP

            Notes
            -----
            - If you're inserting multiple mongoclasses with `insert_one=False` and `ordered=False`, the provided
            mongoclasses will be mutated by setting a `_mongodb_id` attribute with the id coming from
            `InsertManyResult` after this method executes.

            Parameters
            ----------
            `mongoclasses` : Union[object, List[object]]
                A list of mongoclasses or a single mongoclass. When inserting a single mongoclass, you can just do
                `mongoclass.insert()`
            `insert_one` : bool
                Whether to call `mongoclass.insert()` on each mongoclass. Defaults to False. False means it would use
                `Collection.insert_many` to insert all the documents at once.
            `*args, **kwargs` :
                To be passed onto `Collection.insert_many` or `mongoclass.insert()`

            Returns
            -------
            `Union[InsertOneResult, InsertManyResult, List[InsertOneResult]]` :
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
                mongoclasses[0]._mongodb_db,
            )
            insert_result = database[collection].insert_many(
                [x.as_json() for x in mongoclasses], *args, **kwargs
            )
            if kwargs.get("ordered"):
                return insert_result

            for mongoclass, inserted in zip(mongoclasses, insert_result.inserted_ids):
                mongoclass._mongodb_id = inserted

            return insert_result

        insert_many = insert_classes

    return MongoClassClientClass(*args, **kwargs)


def MongoClassClient(*args, **kwargs) -> Union[SupportsMongoClassClient, MongoClient, pymongo.database.Database]:
    """
    Examples:
        >>> from mongoclass import MongoClassClient
        >>> MongoClassClient("test", "mongodb://localhost:27017")
        MongoClient(host=['localhost:27017'], document_class=dict, tz_aware=False, connect=True)

    """
    return client_constructor("pymongo", *args, **kwargs)


warnings.filterwarnings(action="ignore", message="unclosed", category=ResourceWarning)

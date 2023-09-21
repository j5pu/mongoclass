from dataclasses import dataclass

from mongodata import client_constructor

from mongita import MongitaClientDisk
from pymongo import MongoClient

HOSTS = ["localhost:27017", "./mongita"]
DATABASES = ["mongoclass", "coordinates_data", "profiles_list", "mongoclass-test", "coordinates_data-test",
             "profiles_list-test"]


def drop_database(database: str = None) -> None:
    clients = [MongoClient(HOSTS[0]), MongitaClientDisk(HOSTS[1])]
    for client in clients:
        if database:
            client.drop_database(database or DATABASES[0])
        else:
            for d in DATABASES:
                if d in client.list_database_names():
                    client.drop_database(d)


def create_client(engine: str = "pymongo"):

    host = HOSTS[0]
    if engine != "pymongo":
        host = HOSTS[1]

    return client_constructor(engine, host=host, default_db_name=DATABASES[0])


def create_class(cls: str, client, *args, **kwargs):

    if cls == "user":

        @client.mongoclass(*args, **kwargs)
        @dataclass
        class User:
            name: str
            email: str
            phone: int
            country: str = "US"

        return User
    elif cls == "position":

        @client.mongoclass(*args, **kwargs)
        @dataclass
        class Position:
            x: int
            y: int
            z: int

        return Position

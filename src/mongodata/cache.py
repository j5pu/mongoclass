"""Mongo Data Cache Module."""
import json
import threading
import time
from collections.abc import Callable, Generator
from typing import Any

import redis
from redis.lock import Lock


class MongoclassRedisCache:
    """A simple cache system that allows you to cache entire mongoclass collections."""

    def __init__(self, mongoclass_instance, *args, **kwargs) -> None:
        """Init."""
        self.r = redis.Redis(*args, **kwargs)
        self.mongoclass_instance = mongoclass_instance

    # noinspection PyMethodMayBeStatic
    def get_list_name(self, database_name: str, collection_name: str) -> str:
        """Get the name of the list that contains the cached objects."""
        return f"mongoclass:{database_name}:{collection_name}"

    def get_lock(
        self, database_name: str, collection_name: str, *args, **kwargs
    ) -> Lock:
        """Get a lock for a specific mongoclass collection."""
        return self.r.lock(f"lock:{database_name}:{collection_name}", *args, **kwargs)

    def insert_to_cache(self, mongoclass_object: Any) -> None:
        """Insert a new mongoclass instance to the cache of that mongoclass.

        Arguments:
            mongoclass_object: The mongoclass object to insert.
        """
        database_name = mongoclass_object.DATABASE_NAME
        collection_name = mongoclass_object.COLLECTION_NAME

        with self.get_lock(database_name, collection_name):
            serialized = json.dumps(mongoclass_object.as_json())

            self.r.rpush(self.get_list_name(database_name, collection_name), serialized)

    def delete_from_cache(
        self, mongoclass: Any, filter_func: Callable[[Any], bool]
    ) -> bool:
        """Delete a specific object from the cache."""
        item = self.get_from_cache(mongoclass, filter_func)
        if item is None:
            return False

        return bool(
            self.r.lrem(
                self.get_list_name(
                    mongoclass.DATABASE_NAME, mongoclass.COLLECTION_NAME
                ),
                1,
                json.dumps(item.as_json()),
            )
        )

    def get_from_cache(
        self, mongoclass: Any, filter_func: Callable[[Any], bool]
    ) -> object | None:
        """Get a specific object from the cache.

        Arguments:
            mongoclass: The mongoclass class definition (not an instance).
            filter_func: A callable that takes an element from the cache as input and returns a
                boolean value to indicate if it should be returned and finding should be stopped.

        Returns:
            `Optional[object]`: A mongoclass object if the object was found else None.
        """
        for item in self.get_cached(mongoclass):
            if filter_func(item):
                return item
        return None

    def get_cached(
        self, mongoclass: Any, batch_size: int = 500
    ) -> Generator[object, None, None]:
        """Return all cached objects of a mongoclass collection.

        Arguments:
            mongoclass: The mongoclass class definition (not an instance).
            batch_size: How many objects to load at once.

        Yields:
        `object: A mongoclass object.
        """
        last_start = 0
        last_end = batch_size

        list_name = self.get_list_name(
            mongoclass.DATABASE_NAME, mongoclass.COLLECTION_NAME
        )

        while True:
            elements = self.r.lrange(list_name, last_start, last_end)

            if not elements:
                break

            for serialized in elements:
                deserialized = json.loads(serialized)

                yield self.mongoclass_instance.map_document(
                    deserialized, mongoclass.COLLECTION_NAME, mongoclass.DATABASE_NAME
                )

            last_start = last_end + 1
            last_end = last_start + batch_size

    def cache(self, mongoclass: Any, every: int = 0) -> None:
        """Cache the contents of a mongoclass collection.

        Arguments:
        mongoclass: The mongoclass class definition (not an instance).
        every: Re-update the cache every X seconds. Defaults to 0 which means do not
            re-update. Note that you can always call this .cache() method to
            re-update manually. There are update means of updating such as inserting
            into the cache and there are methods for that.
        """
        # Get information for the key
        database_name = mongoclass.DATABASE_NAME
        collection_name = mongoclass.COLLECTION_NAME

        with self.get_lock(database_name, collection_name):

            # Clear the key before caching
            self.r.delete(self.get_list_name(database_name, collection_name))

            pipe = self.r.pipeline()
            for obj in mongoclass.find_classes({}):
                serialized = json.dumps(obj.as_json())

                pipe.rpush(
                    self.get_list_name(database_name, collection_name), serialized
                )
            pipe.execute()

        if every > 0:

            def f():
                while True:
                    self.cache(mongoclass)
                    time.sleep(every)

            threading.Thread(target=f, daemon=True).start()

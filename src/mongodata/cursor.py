"""Mongo Data Cursos Module."""
from collections.abc import Callable

import mongita.command_cursor
import mongita.cursor
import pymongo.command_cursor
import pymongo.cursor
from pymongo.typings import _DocumentType


class Cursor:
    """Cursor."""
    def __init__(
            self,
            cursor: pymongo.cursor.Cursor | (pymongo.command_cursor.CommandCursor[_DocumentType] |
                                             (mongita.command_cursor.CommandCursor | mongita.cursor.Cursor)),
            mapping_function: Callable,
            collection_name: str,
            database_name: str,
            engine_used: str,
    ) -> None:
        """Init."""
        self.internal_cursor = cursor
        self.mapping_function = mapping_function
        self.collection_name = collection_name
        self.database_name = database_name
        self.engine_used = engine_used

    def map_data(self, data: dict):
        """Map data."""
        return self.mapping_function(data, self.collection_name, self.database_name)

    def __iter__(self):
        """Iterate."""
        for data in self.internal_cursor:
            yield self.map_data(data)

    def __next__(self):
        """Next."""
        data = next(self.internal_cursor)
        return self.map_data(data)

    def __getitem__(self, index):
        """Get item."""
        return self.internal_cursor[index]

    def clone(self):
        """Clone."""
        return Cursor(
            self.internal_cursor.clone(),
            self.mapping_function,
            self.collection_name,
            self.database_name,
            self.engine_used,
        )

    def close(self):
        """Close."""
        self.internal_cursor.close()

    def sort(self, key_or_list, direction=None):
        """Sort."""
        self.internal_cursor = self.internal_cursor.sort(key_or_list, direction)
        return self

    def limit(self, limit):
        """Limit."""
        self.internal_cursor = self.internal_cursor.limit(limit)
        return self

    def skip(self, skip):
        """Skip."""
        self.internal_cursor = self.internal_cursor.skip(skip)
        return self

    def max(self, spec):  # noqa: A003
        """Max."""
        self.internal_cursor = self.internal_cursor.max(spec)
        return self

    def min(self, spec):  # noqa: A003
        """Min."""
        self.internal_cursor = self.internal_cursor.min(spec)
        return self

    def where(self, code):
        """Where."""
        self.internal_cursor = self.internal_cursor.where(code)
        return self

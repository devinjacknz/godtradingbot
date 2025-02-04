from typing import Optional


class DatabaseError(Exception):
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(message)
        self.original_error = original_error


class MongoDBError(DatabaseError):
    pass


class PostgreSQLError(DatabaseError):
    pass


class ValidationError(DatabaseError):
    pass


class ConnectionError(DatabaseError):
    pass

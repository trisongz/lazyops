
class SqlTimeout(Exception):
    "Database timeout expired."


class UnknownFileWarning(UserWarning):
    "Warning used by Store.check for unknown files."


class EmptyDirWarning(UserWarning):
    "Warning used by Store.check for empty directories."

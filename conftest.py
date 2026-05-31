"""Root pytest config.

scripts/ holds standalone diagnostic utilities (test_db_connection.py,
test_drive_connection.py) that execute on import and call sys.exit(); despite the
test_ prefix they are not pytest tests. Excluding the directory keeps a repo-root
`pytest` invocation (e.g. the pre-commit hook) from aborting during collection.
"""

collect_ignore_glob = ["scripts/*"]

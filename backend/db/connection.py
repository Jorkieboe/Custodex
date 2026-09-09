import sqlite3
from pathlib import Path
from typing import Union

def get_connection(db_path: Union[str, Path] = ":memory:") -> sqlite3.Connection:
    if isinstance(db_path, Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        db_path_str = str(db_path)
    else:
        db_path_str = db_path
        if db_path_str != ":memory:":
            Path(db_path_str).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path_str, check_same_thread=False)
    conn.row_factory = sqlite3.Row

    with conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        if db_path_str != ":memory:":
            conn.execute("PRAGMA journal_mode = WAL;")

    return conn
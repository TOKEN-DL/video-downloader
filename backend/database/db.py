"""SQLite 连接管理。

用标准库 sqlite3（不引入 aiosqlite，避免为异步 API 引入额外依赖与
线程/事件循环混用问题）：每个线程一个连接，写入用短事务。

数据库路径在**调用时**从 config.DB_PATH 读取，测试才能把它指向临时目录；
模块导入时固化路径会让测试无法替换。
"""
import os
import sqlite3
import threading

import config
from database.models import HISTORY_INDEX_SQL, HISTORY_TABLE_SQL

_local = threading.local()


def _db_path() -> str:
    return config.DB_PATH


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """建表（自愈）：表缺失不会导致 500。"""
    conn.execute(HISTORY_TABLE_SQL)
    for sql in HISTORY_INDEX_SQL:
        conn.execute(sql)
    conn.commit()


def get_conn() -> sqlite3.Connection:
    """取当前线程的连接。路径变了就重开（测试切换临时库时用得上）。"""
    path = _db_path()
    conn = getattr(_local, "conn", None)
    if conn is not None:
        if getattr(_local, "path", None) == path:
            return conn
        conn.close()

    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)

    conn = sqlite3.connect(path, check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    _local.conn = conn
    _local.path = path
    _ensure_schema(conn)
    return conn


def init_db() -> None:
    _ensure_schema(get_conn())


def close_conn() -> None:
    """关闭当前线程的连接（测试清理 / 应用退出用）。"""
    conn = getattr(_local, "conn", None)
    if conn is not None:
        conn.close()
    _local.conn = None
    _local.path = None

import sqlite3
import threading
from abc import ABC, abstractmethod
from collections import deque
from contextlib import contextmanager
from threading import Lock, Condition
from typing import List


# connection = sqlite3.connect('files_info.db')
# cursor = connection.cursor()
#
# cursor.execute('''
#         CREATE TABLE IF NOT EXISTS existing_sha1 (
#             sha1 CHAR(40) PRIMARY KEY
#         )
#     ''')
#
# connection.commit()
# connection.close()


class ResourcePool(ABC):
    def __init__(self, max_resources):
        if max_resources < 1:
            raise ValueError(f'Invalid max_resources argument: {max_resources}')
        self._max_resources = max_resources
        self._request_lock = Lock()
        self._resource_returned = Condition()
        self._pool = deque()
        self._n_resources_created = 0
        self._is_hashable_resource = self.is_hashable_resource()
        self._in_use = set()

    def close(self):
        """Close all resources."""

        with self._request_lock:
            while self._pool:
                self.close_resource(self._pool.popleft())
            while self._in_use:
                self.close_resource(self._in_use.pop())

    def close_resource(self, res):
        """Subclasses should override this method if the resource does
not implement a close method."""
        res.close()

    def __del__(self):
        """Close all resources when the pool is garbage
collected. Note that due to how close is implemented, it may be
called multiple times."""
        self.close()

    def is_hashable_resource(self):
        """Override this function and return False if the resource cannot be
added to a set. Otherwise, we can do some additional error checking and
ensure that all resources are closed when method close is called."""
        return False

    @abstractmethod
    def create_resource(self):
        pass

    def get_resource(self, timeout=None):
        if timeout is None:
            timeout = 50

        with self._request_lock:
            while True:
                if self._pool:
                    res = self._pool.popleft()
                    if self._is_hashable_resource:
                        self._in_use.add(res)
                    return res

                # Can we create another resource?
                if self._n_resources_created < self._max_resources:
                    self._n_resources_created += 1
                    res = self.create_resource()
                    if self._is_hashable_resource:
                        self._in_use.add(res)
                    return res

                # We must wait for a resource to be returned
                with self._resource_returned:
                    if not self._resource_returned.wait(timeout=timeout):
                        raise RuntimeError("Timeout: No available resource in the pool.")
                    # The pool now has at least one resource available and
                    # we will succeed on next iteration.

    def release_resource(self, res):
        if self._is_hashable_resource:
            if res not in self._in_use:
                raise Exception('Releasing unknown object')
            # Could raise exception if two threads are releasing the same resource:
            self._in_use.remove(res)
        self._pool.append(res)
        # Notify the thread waiting for a resource, if any:
        with self._resource_returned:
            self._resource_returned.notify()

    @contextmanager
    def resource(self, timeout=None):
        res = self.get_resource(timeout)
        try:
            yield res
        finally:
            self.release_resource(res)


class ConnectionPool(ResourcePool):
    def __init__(self, max_connections, database, check_same_thread=False):
        super().__init__(max_connections)
        self._database = database
        self.check_same_thread = check_same_thread

    def create_resource(self):
        return sqlite3.connect(database=self._database, check_same_thread=self.check_same_thread)

    def get_connection(self, timeout=None):
        return self.get_resource(timeout)

    def release_resource(self, connection):
        connection.rollback()  # clean up
        return super().release_resource(connection)

    def release_connection(self, connection):
        return self.release_resource(connection)

    def connection(self, timeout=None):
        return self.resource(timeout)


class AbstractDataHandler(ABC):
    def add_sha1(self, sha1: str):
        pass

    def add_all_sha1(self, sha1: set):
        pass

    def check_sha1_exists(self, sha1: str):
        pass

    def get_existing_hash_i(self, hash_list: List[str]) -> List[int]:
        pass


class FilesDBOperations(AbstractDataHandler):
    def __init__(self, source, pool_size=10):
        self.db_name = source
        self.pool = ConnectionPool(max_connections=pool_size, database=self.db_name, check_same_thread=False)

    def add_sha1(self, sha1):
        with self.pool.connection() as conn:
            query = '''
            INSERT INTO hashes (sha1) VALUES (?);
            '''
            try:
                conn.execute(query, (sha1,))
                conn.commit()
            except sqlite3.IntegrityError as e:
                print(e)

    def add_all_sha1(self, sha1: set) -> int:
        with self.pool.connection() as conn:
            query = '''
                       INSERT OR IGNORE INTO hashes (sha1) VALUES (?);
                       '''
            try:
                with conn:
                    cursor = conn.cursor()
                    conn.executemany(query, [(s,) for s in sha1])
                    new_values = cursor.rowcount
                    return new_values
            except sqlite3.IntegrityError as e:
                print(f"Error: {e}")

    def check_sha1_exists(self, sha1: str):
        with self.pool.connection() as conn:
            query = '''
            SELECT COUNT(*) FROM hashes WHERE sha1 = ?;
            '''
            result = conn.execute(query, (sha1,)).fetchone()[0]
            return result > 0

    def get_existing_hash_i(self, hash_list: List[str]) -> List[int]:
        temple_table_name = f"temp_t_{threading.current_thread().ident}"

        with self.pool.connection() as conn:
            conn.execute(
                f"""
                CREATE TEMPORARY TABLE {temple_table_name} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hash CHAR(40)
                )
                """
            )

            conn.executemany(
                f"INSERT INTO {temple_table_name} (hash) VALUES (?)",
                [(hash_value,) for hash_value in hash_list]
            )

            conn.commit()

            query = f"""
                SELECT id 
                FROM {temple_table_name} 
                WHERE hash IN (SELECT sha1 FROM hashes)
            """

            result = conn.execute(query).fetchall()

            indexes_for_given_hashes = [index[0] - 1 for index in result]

            conn.execute(f"DROP TABLE {temple_table_name}")

            return indexes_for_given_hashes
    # def get_existing_hash_i(self, hash_list: List[str]) -> List[int]:
    #     with self.pool.connection() as conn:
    #         temple_table_name = f"temp_t_{threading.current_thread().ident}"
    #         conn.execute(f"CREATE TEMPORARY TABLE {temple_table_name} ("
    #                      f"id INTEGER PRIMARY KEY AUTOINCREMENT,"
    #                      f"hash CHAR(40)"
    #                      f")")
    #         conn.commit()
    #
    #         conn.executemany(f"INSERT INTO {temple_table_name} (hash) VALUES (?)",
    #                          [(hash_value,) for hash_value in hash_list])
    #         conn.commit()
    #         temp_data = conn.execute(f"SELECT * FROM {temple_table_name}").fetchall()
    #         print(temp_data)
    #
    #         query = f"""
    #             SELECT hash
    #             FROM {temple_table_name}
    #             WHERE hash IN (SELECT sha1 FROM hashes)
    #         """
    #
    #         result = conn.execute(query).fetchall()
    #         indexes_for_given_hashes = [index[0] for index in result]
    #         # for i, ind in enumerate(indexes_for_given_hashes):
    #         #     indexes_for_given_hashes[i] = ind
    #
    #         conn.execute(f"DROP TABLE {temple_table_name}")
    #         return indexes_for_given_hashes

    # def close_connection(self):
    #     conn.close()

# if __name__ == "__main__":
#     info = FilesDBOperations("files_info.db")
#     for line in My_io.read_file_line_generator('C:\\Users\\T-k\\PycharmProjects\\VtParser\\Resources\\sha1_base.txt'):
#         info.add_sha1(line)

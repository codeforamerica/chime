import os
import time
import fcntl
import errno


class SimpleFlock:
    """Provides the simplest possible interface to flock-based file locking. Intended for use with the `with` syntax. It will create/truncate/delete the lock file as necessary."""

    def __init__(self, path, timeout=None):
        self._path = path
        self._timeout = timeout
        self._fd = None

    def __enter__(self):
        self._fd = os.open(self._path, os.O_CREAT)
        start_lock_search = time.time()
        while True:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                # Lock acquired!
                return
            except IOError, ex:
                if ex.errno != errno.EAGAIN:  # Resource temporarily unavailable
                    raise
                elif self._timeout is not None and time.time() > (start_lock_search + self._timeout):
                    # Exceeded the user-specified timeout.
                    raise

            time.sleep(0.01)

    def __exit__(self, *args):
        fcntl.flock(self._fd, fcntl.LOCK_UN)
        os.close(self._fd)
        self._fd = None

"""Child processes: launch with explicit environment, measure and kill the whole tree."""
import os
import signal
import socket
import subprocess
import sys
import time
from multiprocessing.connection import Connection

import psutil

from ._child import THREAD_VARIABLES


class ChildProcess:
    """One job process in its own session, reachable over a socket pair."""

    def __init__(self, *, warm, threads, extra_env=None):
        parent, child = socket.socketpair()
        env = dict(os.environ)
        env.update({name: str(threads) for name in THREAD_VARIABLES})
        env.update({'NUMEK_CHILD_FD': str(child.fileno()), 'NUMEK_CHILD_MODE': 'warm' if warm else 'isolated',
                    'NUMEK_JOB_THREADS': str(threads), 'PYTHONDONTWRITEBYTECODE': '1'})
        env.update(extra_env or {})
        self.process = subprocess.Popen(
            [sys.executable, '-m', 'numek_platform.execution._child'], env=env, pass_fds=(child.fileno(),),
            start_new_session=True, stdin=subprocess.DEVNULL)
        child.close()
        self.connection = Connection(parent.detach())
        self.warm = warm
        self.threads = threads
        self.jobs_run = 0
        self.started = time.monotonic()

    @property
    def pid(self):
        return self.process.pid

    def alive(self):
        return self.process.poll() is None

    def tree_rss(self):
        """Resident memory of the process and all its descendants."""
        try:
            root = psutil.Process(self.process.pid)
            members = [root, *root.children(recursive=True)]
        except psutil.NoSuchProcess:
            return 0
        total = 0
        for member in members:
            try:
                total += member.memory_info().rss
            except psutil.NoSuchProcess:
                pass
        return total

    def send(self, message):
        self.connection.send(message)

    def poll(self, timeout):
        try:
            return self.connection.poll(timeout)
        except (OSError, EOFError):
            return False

    def recv(self):
        return self.connection.recv()

    def kill(self, grace=2.0):
        """Terminate the whole process group, escalating to SIGKILL."""
        if self.alive():
            for sig, wait in ((signal.SIGTERM, grace), (signal.SIGKILL, 5.0)):
                try:
                    os.killpg(self.process.pid, sig)
                except ProcessLookupError:
                    break
                try:
                    self.process.wait(wait)
                    break
                except subprocess.TimeoutExpired:
                    continue
        else:
            try:  # reap descendants that outlived their leader
                os.killpg(self.process.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
        try:
            self.connection.close()
        except OSError:
            pass

    def close(self):
        """Ask a warm process to exit cleanly, then make sure it did."""
        try:
            self.send(('exit', None))
            self.process.wait(5)
        except Exception:
            pass
        self.kill()

"""SSH helpers for driving the CloudLab nodes."""

import shlex
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor

SSH_OPTS = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=15",
            "-o", "ServerAliveInterval=15"]


class RemoteError(RuntimeError):
    pass


class Node:
    def __init__(self, name, ssh):
        self.name = name
        self.ssh = ssh

    def run(self, cmd, timeout=120, check=True):
        """Runs a shell command on the node; returns its stdout."""
        p = subprocess.run(["ssh"] + SSH_OPTS + [self.ssh, cmd],
                           capture_output=True, text=True, timeout=timeout)
        if check and p.returncode != 0:
            raise RemoteError("%s: command failed (%d): %s\n%s" % (
                self.name, p.returncode, cmd[:200], (p.stdout + p.stderr)[-2000:]))
        return p.stdout

    def bg(self, cmd, log):
        """Starts a command in the background on the node, output to log."""
        self.run("nohup bash -c %s > %s 2>&1 < /dev/null &" % (shlex.quote(cmd), log),
                 timeout=30)

    def put(self, text, path):
        """Writes text to a file on the node."""
        p = subprocess.run(["ssh"] + SSH_OPTS + [self.ssh, "cat > %s" % shlex.quote(path)],
                           input=text, capture_output=True, text=True, timeout=60)
        if p.returncode != 0:
            raise RemoteError("%s: writing %s failed: %s" % (self.name, path, p.stderr))

    def wait_for(self, path, pattern, timeout, fail_pattern=None):
        """Waits until a line matching pattern appears in a file on the node."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            out = self.run("grep -E %s %s 2>/dev/null | head -1" % (
                shlex.quote(pattern), path), check=False)
            if out.strip():
                return out.strip()
            if fail_pattern:
                bad = self.run("grep -E %s %s 2>/dev/null | head -1" % (
                    shlex.quote(fail_pattern), path), check=False)
                if bad.strip():
                    raise RemoteError("%s: %s" % (self.name, bad.strip()))
            time.sleep(0.5)
        tail = self.run("tail -15 %s" % path, check=False)
        raise RemoteError("%s: timed out waiting for /%s/ in %s\n%s" % (
            self.name, pattern, path, tail))


def copy_between(src, src_path, dst, dst_path):
    """Copies a file from one node to another through this machine."""
    p = subprocess.run(["scp", "-q", "-3"] + SSH_OPTS +
                       ["%s:%s" % (src.ssh, src_path), "%s:%s" % (dst.ssh, dst_path)],
                       capture_output=True, text=True, timeout=300)
    if p.returncode != 0:
        raise RemoteError("copy %s -> %s failed: %s" % (src.name, dst.name, p.stderr))


def parallel(fn, items):
    """Runs fn on each item concurrently; re-raises the first failure."""
    with ThreadPoolExecutor(max_workers=len(items)) as ex:
        return [f.result() for f in [ex.submit(fn, i) for i in items]]

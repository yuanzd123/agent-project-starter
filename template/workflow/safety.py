"""Filesystem and subprocess boundaries. This module is not an OS sandbox."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import signal
import subprocess
import tempfile
import time

IGNORED = {'.git', '.local', '__pycache__'}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode('utf-8')


def relative(root, name):
    if not isinstance(name, str) or not name or '\\' in name or ':' in name or '\x00' in name:
        raise ValueError('Use an explicit repository-relative POSIX file path')
    path = PurePosixPath(name)
    if (not path.parts or path.is_absolute() or '..' in path.parts or name != path.as_posix()
            or any(part in IGNORED for part in path.parts) or path.suffix == '.pyc'):
        raise ValueError('Path escapes allowed working files')
    result = root / name
    if any(p.is_symlink() for p in (result, *result.parents)):
        raise ValueError('Symlink paths are not allowed')
    if not result.resolve().is_relative_to(root):
        raise ValueError('Path escapes repository')
    return result


def snapshot(root):
    files = {}
    for base, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in IGNORED)
        for name in [*dirs, *sorted(names)]:
            path = Path(base) / name
            if path.is_symlink():
                raise ValueError('Workflow requires a working tree without symlinks')
            if path.is_file() and path.suffix == '.pyc':
                continue
            if path.is_file():
                files[path.relative_to(root).as_posix()] = {
                    'sha256': digest(path.read_bytes()), 'executable': bool(path.stat().st_mode & 0o111)}
            elif not path.is_dir():
                raise ValueError('Only regular working files are supported')
    return files


def content_hash(root):
    return digest(canonical(snapshot(root)))


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() or any(p.is_symlink() for p in path.parents):
        raise ValueError('State directory must not contain symlinks')
    fd, temporary = tempfile.mkstemp(prefix='.write-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(canonical(value))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def clean_env(allow=()):
    names = {'PATH', 'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'LANG', 'LC_ALL', 'PATHEXT'} | set(allow)
    env = {key: value for key, value in os.environ.items() if key in names}
    env['PYTHONUTF8'] = '1'
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    return env


def execute(argv, cwd, timeout, payload=None, cancel=lambda: False, env=None, output_limit=1048576):
    """No shell. Bound output and kill the process group on finish, timeout or cancel."""
    started = time.monotonic()
    with tempfile.TemporaryFile() as stdin, tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        if payload is not None:
            stdin.write(canonical(payload))
        stdin.seek(0)
        flags = {'start_new_session': True} if os.name == 'posix' else {
            'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP}
        try:
            proc = subprocess.Popen(argv, cwd=cwd, stdin=stdin, stdout=stdout, stderr=stderr,
                                    env=clean_env() if env is None else env, shell=False, **flags)
        except OSError:
            return {'kind': 'infrastructure', 'exit_code': None, 'stdout': '', 'stderr': '',
                    'seconds': time.monotonic() - started}
        kind = 'completed'
        try:
            while proc.poll() is None:
                if cancel():
                    kind = 'cancelled'
                    break
                if time.monotonic() - started >= timeout:
                    kind = 'timeout'
                    break
                if os.fstat(stdout.fileno()).st_size + os.fstat(stderr.fileno()).st_size > output_limit:
                    kind = 'output_limit'
                    break
                time.sleep(0.01)
        finally:
            if os.name == 'posix':
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            elif proc.poll() is None:
                try:
                    subprocess.run(['taskkill', '/PID', str(proc.pid), '/T', '/F'],
                                   capture_output=True, timeout=10, check=False, env=clean_env())
                except (OSError, subprocess.TimeoutExpired):
                    pass
                finally:
                    if proc.poll() is None:
                        proc.kill()
            proc.wait(timeout=10)
        stdout.seek(0)
        stderr.seek(0)
        out, err = stdout.read(output_limit + 1), stderr.read(output_limit + 1)
        if len(out) + len(err) > output_limit:
            kind = 'output_limit'
        return {'kind': kind, 'exit_code': proc.returncode,
                'stdout': out[:output_limit].decode('utf-8', errors='replace'),
                'stderr': err[:output_limit].decode('utf-8', errors='replace'),
                'seconds': time.monotonic() - started}

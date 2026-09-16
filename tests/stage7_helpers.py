from contextlib import contextmanager
from pathlib import Path
import shutil
from typing import Iterator
from uuid import uuid4


@contextmanager
def workspace_temp_directory() -> Iterator[str]:
    """Create an isolated temporary directory without Windows tempfile ACLs."""

    path = Path.cwd() / f".stage7-test-{uuid4().hex}"
    path.mkdir()
    try:
        yield str(path)
    finally:
        shutil.rmtree(path)

import asyncio
import concurrent.futures
from typing import Awaitable, TypeVar, Callable, Iterable, TextIO
from pathlib import Path
import shutil
import contextlib
import tempfile

_FS_POOL = concurrent.futures.ThreadPoolExecutor(8)  # pylint: disable=consider-using-with

T = TypeVar('T')


def _run_fs_op(op: Callable[[], T]) -> Awaitable[T]:
    return asyncio.get_running_loop().run_in_executor(_FS_POOL, op)


async def remove_directory(dirpath: Path) -> None:
    await _run_fs_op(lambda: shutil.rmtree(dirpath))


def _remove_files(files: Iterable[Path]) -> None:
    for f in files:
        print(f'Remove [{f}]')
        f.unlink()


async def remove_files(files: Iterable[Path]) -> None:
    await _run_fs_op(lambda: _remove_files(files))


def _move_files(*, into: Path, files: Iterable[Path], whence: Path) -> None:
    files = list(files)
    for src_path in files:
        relpath = src_path.relative_to(whence)
        if relpath.parts[0] == '..':
            raise RuntimeError(f'Cannot move file [{src_path}] relative to non-parent directory at [{whence}]')

        dest_path = into / relpath

        if src_path.is_dir():
            dest_path.mkdir(exist_ok=True, parents=True)
        else:
            dest_path.parent.mkdir(exist_ok=True, parents=True)
            print(f'Move [{src_path}] \n  to [{dest_path}]')
            src_path.rename(dest_path)


async def move_files(*, into: Path, files: Iterable[Path], whence: Path) -> None:
    await _run_fs_op(lambda: _move_files(into=into, files=files, whence=whence))


def _copy_files(*, into: Path, files: Iterable[Path], whence: Path) -> None:
    files = list(files)
    for src_path in files:
        relpath = src_path.relative_to(whence)
        if relpath.parts[0] == '..':
            raise RuntimeError(f'Cannot copy file [{src_path}] relative to non-parent directory at [{whence}]')

        dest_path = into / relpath

        if src_path.is_dir():
            dest_path.mkdir(exist_ok=True, parents=True)
        else:
            dest_path.parent.mkdir(exist_ok=True, parents=True)
            print(f'Copy [{src_path}] \n  to [{dest_path}]')
            shutil.copy2(src_path, dest_path)


async def copy_files(*, into: Path, files: Iterable[Path], whence: Path) -> None:
    await _run_fs_op(lambda: _copy_files(into=into, files=files, whence=whence))

async def filter_file_contents(*, files: Iterable[Path], fn: Callable[[TextIO, TextIO], None]):
    def impl():
        for input_file in files:
            with contextlib.ExitStack() as stack:
                input_fh = stack.enter_context(input_file.open("r", encoding="UTF-8"))
                output_fh = stack.enter_context(tempfile.NamedTemporaryFile("w", encoding="UTF-8", delete=False))
                output_file = Path(output_fh.name)

                fn(input_fh, output_fh)

            print(f"Filtered {input_file} (via f{output_file})")
            output_file.rename(input_file)

    await _run_fs_op(impl)

import itertools
from contextlib import asynccontextmanager
import json
from pathlib import Path, PurePosixPath
from semver import VersionInfo
import zipfile
from typing import NamedTuple, AsyncIterator, Sequence
import aiohttp.client

from dds_ports import port, util


class SQLite3VersionGroup(NamedTuple):
    year: int
    major: int
    minor: int
    patches: Sequence[int]


VERSION_GROUPS = [
    SQLite3VersionGroup(2021, 3, 35, [0, 1, 2, 3, 4]),
    SQLite3VersionGroup(2021, 3, 34, [1]),
    SQLite3VersionGroup(2020, 3, 34, [0]),
    SQLite3VersionGroup(2020, 3, 33, [0]),
    SQLite3VersionGroup(2020, 3, 32, [0, 1, 2, 3]),
    SQLite3VersionGroup(2020, 3, 31, [0, 1]),
    SQLite3VersionGroup(2019, 3, 30, [0, 1]),
    SQLite3VersionGroup(2019, 3, 29, [0]),
    SQLite3VersionGroup(2019, 3, 28, [0]),
    SQLite3VersionGroup(2019, 3, 27, [0, 1, 2]),
    SQLite3VersionGroup(2018, 3, 26, [0]),
    SQLite3VersionGroup(2018, 3, 25, [0]),
    SQLite3VersionGroup(2018, 3, 24, [0]),
    SQLite3VersionGroup(2018, 3, 23, [0, 1]),
    SQLite3VersionGroup(2018, 3, 22, [0]),
    SQLite3VersionGroup(2017, 3, 21, [0]),
    SQLite3VersionGroup(2017, 3, 20, [0, 1]),
    SQLite3VersionGroup(2017, 3, 19, [0, 1, 2, 3]),
    # SQLite3VersionGroup(2017, 3, 18, [0, 1, 2]),
    # SQLite3VersionGroup(2017, 3, 17, [0]),
    # SQLite3VersionGroup(2017, 3, 16, [0, 1, 2]),
    # SQLite3VersionGroup(2016, 3, 15, [0, 1, 2]),
    # SQLite3VersionGroup(2016, 3, 14, [0, 1, 2]),
    # SQLite3VersionGroup(2016, 3, 13, [0]),
    # SQLite3VersionGroup(2016, 3, 12, [0, 1, 2]),
    # SQLite3VersionGroup(2016, 3, 11, [0, 1]),
    # SQLite3VersionGroup(2016, 3, 10, [0, 1, 2]),
]

CONFIGS = [
    ('SQLITE_THREADSAFE', 2),
    ('SQLITE_OMIT_LOAD_EXTENSION', 1),
    ('SQLITE_OMIT_DEPRECATED', 1),
    ('SQLITE_DEFAULT_MEMSTATUS', 0),
    ('SQLITE_DQS', 0),
]

tmpl = r'''
#ifndef {macro}
#define {macro} {default}
#endif
'''

DEFAULT_CONFIG = ''.join(tmpl.format(macro=m, default=d) for m, d in CONFIGS)

SRC_PREFIX = r'''
/**
 * The contents of this preamble are not part of the main sqlite3 distribution,
 * and are inserted as part of the dds port for sqlite3.
 */

#if defined(__has_include)
#  if __has_include(<sqlite3.tweaks.h>)
#    include <sqlite3.tweaks.h>
#  endif
#endif

''' + DEFAULT_CONFIG + r'''

/** End of dds-inserted configuration preamble */

'''


async def prep_sqlite3_dir(destdir: Path, url: str) -> None:
    topdir = PurePosixPath(url).with_suffix('').name
    with util.temporary_directory() as tmpdir:
        zip_dest = tmpdir / 'archive.zip'
        async with aiohttp.client.ClientSession() as sess:
            resp = await sess.get(url)
            resp.raise_for_status()
            with zip_dest.open('wb') as ofd:
                while 1:
                    buf = await resp.content.read(1024)
                    if not buf:
                        break
                    ofd.write(buf)

        zf = zipfile.ZipFile(zip_dest)
        destdir.joinpath('src/sqlite3').mkdir(exist_ok=True, parents=True)
        for fname in ('sqlite3.h', 'sqlite3.c', 'sqlite3ext.h'):
            with zf.open(f'{topdir}/{fname}') as sf:
                content = sf.read()
                content = SRC_PREFIX.encode() + content
                destdir.joinpath('src/sqlite3', fname).write_bytes(content)


class SQLite3Port:
    def __init__(self, year: int, version: VersionInfo) -> None:
        self.year = year
        self.version = version
        self.package_id = port.PackageID('sqlite3', version)

    @asynccontextmanager
    async def prepare_sdist(self) -> AsyncIterator[Path]:
        ver = self.version
        url = f'https://sqlite.org/{self.year}/sqlite-amalgamation-{ver.major}{ver.minor:0>2}{ver.patch:0>2}00.zip'

        with util.temporary_directory() as tmpdir:
            await prep_sqlite3_dir(tmpdir, url)
            tmpdir.joinpath('package.json').write_text(
                json.dumps({
                    'name': 'sqlite3',
                    'namespace': 'sqlite3',
                    'version': str(self.version),
                }))
            tmpdir.joinpath('library.json').write_text(json.dumps({'name': 'sqlite3'}))
            yield tmpdir


async def all_ports() -> port.PortIter:
    quads = itertools.chain.from_iterable((
        (grp.year, grp.major, grp.minor, patch)  #
        for patch in grp.patches  #
    ) for grp in VERSION_GROUPS)
    return (
        SQLite3Port(year, VersionInfo(major, minor, patch))  #
        for year, major, minor, patch in quads  #
    )

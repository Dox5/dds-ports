from dds_ports import port, git, fs

from semver import VersionInfo

from typing import AsyncIterator
import contextlib
import json
import pathlib
import re

class TayweeArgsPort:
    GIT_URL = "https://github.com/taywee/args"

    def __init__(self, version):
        self._package_id = port.PackageID("taywee-args", VersionInfo.parse(version))
        self._tag = version

    @property
    def package_id(self):
        return self._package_id

    def _write_package_json(self, root):
        package = {
            "name": self.package_id.name,
            "version": str(self.package_id.version),
            "namespace": "taywee",
        }

        with (root/"package.json").open("w", encoding="UTF-8") as package_file:
            json.dump(package, package_file, indent=True)

    def _write_library_jsons(self, root):
        library = {
            "name": "args",
        }

        with (root/"library.json").open("w", encoding="UTF-8") as library_file:
            json.dump(library, library_file, indent=4)

    async def _munge_files_into_libs(self, root):
        # These tests are not easy to immediatly turn into DDS compatible tests
        await fs.remove_directory(root/"test")
        await fs.remove_files([root/"catch.hpp"])

        await fs.move_files(
            files=[root/"args.hxx"],
            into=root/"include",
            whence=root,
        ),

        await fs.move_files(
            files=[root/"test.cxx"],
            into=root/"src",
            whence=root,
        ),

        (root/"src"/"test.cxx").rename(root/"src"/"args.test.cxx")

    async def _rewrite_includes(self, root):
        src_include = re.compile(r'^(#include\s+["<])(catch.hpp[>"])')

        def fix_catch_include(in_fh, out_fh):
            for line in in_fh:
                line = src_include.sub(r"\1catch2/\2", line)
                if not line.startswith("#define CATCH_CONFIG_MAIN"):
                    out_fh.write(line)

        await fs.filter_file_contents(
            files=root.glob("test/*.cxx"),
            fn=fix_catch_include)

    @contextlib.asynccontextmanager
    async def prepare_sdist(self) -> AsyncIterator[pathlib.Path]:
        async with git.temporary_git_clone(TayweeArgsPort.GIT_URL, self._tag) as tdir:
            await self._munge_files_into_libs(tdir)
            self._write_package_json(tdir)
            self._write_library_jsons(tdir)
            await self._rewrite_includes(tdir)
            yield tdir

async def all_ports() -> port.PortIter:
    versions = [ ("6.2.7") ]
    return [TayweeArgsPort(version) for version in versions]

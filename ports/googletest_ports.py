from dds_ports import port, git, fs

from semver import VersionInfo

from typing import AsyncIterator
import contextlib
import json
import pathlib
import re

class GoogleTestPort:
    GIT_URL = "https://github.com/google/googletest"

    def __init__(self, tag, version):
        self._package_id = port.PackageID("googletest", VersionInfo.parse(version))
        self._tag = tag

    @property
    def package_id(self):
        return self._package_id

    def _write_package_json(self, root):
        package = {
            "name": self.package_id.name,
            "version": str(self.package_id.version),
            "namespace": "googletest",
            "depends": [
                "abseil@2021.3.24",
            ]
        }

        with (root/"package.json").open("w", encoding="UTF-8") as package_file:
            json.dump(package, package_file, indent=True)

    def _write_library_jsons(self, root):
        library_contents = {
            "gtest":      ["abseil/abseil"],
            "gtest-main": ["abseil/abseil", "googletest/gtest"],
            "gmock":      ["abseil/abseil", "googletest/gtest"],
            "gmock-main": ["abseil/abseil", "googletest/gmock"],
        }

        for library_name, uses in library_contents.items():
            library = {
                "name": library_name,
                "uses": uses,
            }

            library_path = root/"libs"/library_name/"library.json"

            with library_path.open("w", encoding="UTF-8") as library_file:
                json.dump(library, library_file, indent=4)

    async def _munge_files_into_libs(self, root):
        await fs.move_files(
            files=root.glob("googlemock/include/**/*"),
            into=root/"libs"/"gmock",
            whence=root/"googlemock",
        ),

        await fs.move_files(
            files=root.glob("googlemock/src/**/*"),
            into=root/"libs"/"gmock",
            whence=root/"googlemock",
        ),

        await fs.move_files(
            files=root.glob("googletest/include/**/*"),
            into=root/"libs"/"gtest",
            whence=root/"googletest",
        ),

        await fs.move_files(
            files=root.glob("googletest/src/**/*"),
            into=root/"libs"/"gtest",
            whence=root/"googletest",
        ),

        await fs.remove_files([root/"library.json"])

        if (root/"docs").exists():
            await fs.remove_directory(root/"docs")
        await fs.remove_directory(root/"ci")
        await fs.remove_directory(root/"googletest")
        await fs.remove_directory(root/"googlemock")


        # Done so as to avoid races
        await fs.move_files(
            files=[root/"libs"/"gmock"/"src"/"gmock_main.cc"],
            into=root/"libs"/"gmock-main"/"src",
            whence=root/"libs"/"gmock",
        )

        await fs.move_files(
            files=[root/"libs"/"gtest"/"src"/"gtest_main.cc"],
            into=root/"libs"/"gtest-main"/"src",
            whence=root/"libs"/"gtest",
        )

    async def _rewrite_includes(self, root):
        src_include = re.compile(r'^(\s*#include\s+")src/')

        def del_src_from_inc(in_fh, out_fh):
            for line in in_fh:
                line = src_include.sub(r"\1", line)
                out_fh.write(line)

        await fs.filter_file_contents(
            files=root.glob("**/*.cc"),
            fn=del_src_from_inc)




    @contextlib.asynccontextmanager
    async def prepare_sdist(self) -> AsyncIterator[pathlib.Path]:
        async with git.temporary_git_clone(GoogleTestPort.GIT_URL, self._tag) as tdir:
            await self._munge_files_into_libs(tdir)
            self._write_package_json(tdir)
            self._write_library_jsons(tdir)
            await self._rewrite_includes(tdir)
            yield tdir

async def all_ports() -> port.PortIter:
    tags = [
        ("release-1.11.0", "1.11.0"),
        ("release-1.10.0", "1.10.0"),
    ]

    googltest_ports = [GoogleTestPort(tag, version) for tag, version in tags]
    return googltest_ports

#! /usr/bin/env python
#
# Copyright (C) 2012 Nuxeo
#

import sys
from datetime import datetime

from distutils.core import setup
scripts = ["nuxeo-drive-client/bin/ndrive"]
freeze_options = {}

name = 'nuxeo-drive'
packages = [
    'nxdrive',
    'nxdrive.tests',
    'nxdrive.gui',
]
version = '0.1.0'
if '--dev' in sys.argv:
    # timestamp the dev artifacts for continuous integration
    # distutils only accepts "b" + digit
    sys.argv.remove('--dev')
    timestamp = datetime.utcnow().isoformat()
    timestamp = timestamp.replace(":", "")
    timestamp = timestamp.replace(".", "")
    timestamp = timestamp.replace("T", "")
    timestamp = timestamp.replace("-", "")
    version += "b" + timestamp


if '--freeze' in sys.argv:
    print "Building standalone executable..."
    sys.argv.remove('--freeze')
    from cx_Freeze import setup, Executable
    from cx_Freeze.windist import bdist_msi  # monkeypatch to add options

    # build_exe does not seem to take the package_dir info into account
    sys.path.append('nuxeo-drive-client')

    base = None
    if sys.platform == "win32":
        base = "Win32GUI"
    executables = [Executable(s, base=base) for s in scripts]
    scripts = []
    freeze_options = dict(
        executables=executables,
        options={
            "build_exe": {
                "packages": packages + [
                    "PySide.QtGui",
                    "atexit",  # implicitly required by PySide
                    "sqlalchemy.dialects.sqlite",
                    "nose",
                ],
                "excludes": [
                    "ipdb",
                    "clf",
                    "IronPython",
                    "pydoc",
                    "tkinter",
                ],
            },
            "bdist_msi": {
                "add_to_path": True,
                "upgrade_code": name + '--' + version,
            },
        },
    )
    # TODO: investigate with esky to get an auto-updateable version but
    # then make sure that we can still have .msi and .dmg packages
    # instead of simple zip files.


setup(
    name=name,
    version=version,
    description="Desktop synchronization client for Nuxeo.",
    author="Olivier Grisel",
    author_email="ogrisel@nuxeo.com",
    url='http://github.com/nuxeo/nuxeo-drive',
    packages=packages,
    package_dir={'nxdrive': 'nuxeo-drive-client/nxdrive'},
    scripts=scripts,
    long_description=open('README.rst').read(),
    **freeze_options
)
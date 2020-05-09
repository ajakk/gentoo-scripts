#!/usr/bin/env python

from gentoopm import get_package_manager

from gpyutils.implementations import get_python_impls, read_implementations
from gpyutils.packages import group_packages

import sys

#
# This is mostly torn out of
# https://github.com/mgorny/gpyutils/blob/master/gpy-showimpls.
# There's probably lots of room for simplification.
#

pm = get_package_manager()
read_implementations(pm)

if len(sys.argv) < 2:
    print("Usage: `{} atom`".format(sys.argv[0]))
    sys.exit(0)

pkgs = group_packages(pm.repositories['gentoo'].filter(sys.argv[1]).sorted)

for pkg in pkgs:
    for ver in pkg:
        output = "{0}: ".format(ver)
        impls = get_python_impls(ver)

        if not impls:
            continue

        for i in impls:
            output += "{} ".format(i.short_name)

        print(output.strip())

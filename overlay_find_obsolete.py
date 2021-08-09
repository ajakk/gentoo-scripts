#!/usr/bin/env python

import sys

import pkgcore.config
from pkgcore.ebuild import atom as atom_mod


def find_obsolete_packages(primary, secondary):
    """
    Find packages in secondary whose versions are all superceded by
    package versions in primary
    """
    for category in secondary.packages:
        for package in secondary.packages[category]:
            cp = '{}/{}'.format(category, package)
            secondary_pkg = secondary.match(atom_mod.atom(cp))
            primary_pkg = primary.match(atom_mod.atom(cp))

            if not primary_pkg:
                print("Primary repo doesn't have '{}', ignoring".format(cp))
                continue

            # If the maximum in the secondary repo is lesser than the
            # minimum of the packages in the primary repo, then the
            # primary repo fully supercedes the packages in the
            # secondary repo and the package may no longer be
            # necessary in the secondary repo
            if max(secondary_pkg) < min(primary_pkg):
                yield cp


def main(primary, secondary):
    primary_repo = pkgcore.config.load_config().repo[primary]
    secondary_repo = pkgcore.config.load_config().repo[secondary]
    print('\n'.join(sorted(find_obsolete_packages(primary_repo,
                                                  secondary_repo))))

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])

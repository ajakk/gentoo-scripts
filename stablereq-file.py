#!/usr/bin/env python

from configparser import ConfigParser
import os
import sys

import requests

import pkgcore.config
from pkgcore.ebuild import atom as atom_mod

BZ_API = "https://bugs.gentoo.org/rest/bug"


def cpv_to_atom(cpv):
    repo = pkgcore.config.load_config().repo['gentoo']
    atom = atom_mod.atom('=' + cpv)
    return repo.match(atom)[0]


def atom_maints(atom) -> list:
    # Get list of strings per maintainer object
    strings = [str(maint) for maint in atom.maintainers]

    # Slice off the name, get the <email>
    mails = [maint.split(" ")[-1] for maint in strings]

    # Return list of plain emails
    return [mail.replace("<", "").replace(">", "") for mail in mails]


def file_stablereq(session, cpv):
    params = {
        "Bugzilla_api_key": apikey,

        "product": "Gentoo Linux",
        "component": "Stabilization",
        "version": "unspecified",
        "description": "Please stabilize.",
        "summary": cpv + ": stabilization",
        "cf_stabilisation_atoms": cpv + " *",
        "keywords": ["STABLEREQ"]
    }

    atom = cpv_to_atom(cpv)

    maintainers = atom_maints(atom)

    params["assigned_to"] = maintainers[0]

    if len(maintainers) > 1:
        params["cc"] = maintainers[1:]

    import pdb; pdb.set_trace()

    req = session.post(BZ_API, params=params)

    print(req.json()['id'])


if __name__ == "__main__":
    session = requests.Session()
    bugzrc = os.path.expanduser("~/.bugzrc")

    if not os.path.isfile(bugzrc):
        print("Can't access {}".format(bugzrc))
        sys.exit(-1)

    config = ConfigParser()
    config.read(bugzrc)
    apikey = config['default']['key']

    file_stablereq(session, sys.argv[1])

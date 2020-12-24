#!/usr/bin/env python

from configparser import ConfigParser
import os
import requests
import subprocess
import sys

import pkgcore.config
from pkgcore.ebuild import atom as atom_mod

BZ_API = "https://bugs.gentoo.org/rest/{endpoint}"


def run_shell(string):
    command = string.split()
    process = subprocess.Popen(command, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL)
    stdout, stderr = process.communicate()
    return stdout


def get_package_list(old, new):
    stdout = run_shell("gpy-upgrade-impl -m -s {} {}".format(old, new))

    # stdout is newline separated string of strings like "cat/pkg [maint1
    # maint2]", here we split the string by newlines and drop everything after
    # the first space per item. This loses the maintainer information, but we
    # can get that from elsewhere
    return [x.split(" ")[0] for x in stdout.decode().split("\n") if x]


def find_stablereqs(session, cpv) -> list:
    params = {
        # Search for cpv as a substring of cf_stabilisation_atoms
        "v1": cpv,
        "o1": "substring",
        "f1": "cf_stabilisation_atoms",

        # But ignore keywording bugs
        "f2": "component",
        "o2": "notequals",
        "v2": "Keywording",

        "resolution": "---"
    }

    print("Searching for stabilization bugs including {}".format(cpv))
    req = session.get(BZ_API.format(endpoint="bug"), params=params)
    bugs = req.json()['bugs']
    return bugs


def find_normal_use(repo, cp):
    atom = atom_mod.atom(cp + '[python_targets_python3_8]')
    return repo.match(atom)


def find_single_use(repo, cp):
    atom = atom_mod.atom(cp + '[python_single_target_python3_8]')
    return repo.match(atom)


def find_python_compat(repo, cp):
    atom = atom_mod.atom(cp)
    matches = []

    for pkg in repo.match(atom):
        # Environment is straight from the environment file, a hacky solution
        # is catching if the python implementation is in that
        line = [line for line in pkg.environment.data.split('\n')
                if "PYTHON_COMPAT=" in line][0]

        if "python3_8" in line:
            matches.append(pkg)

    return matches


def get_suitable_version(cpv):
    repo = pkgcore.config.load_config().repo['gentoo']

    matches = find_normal_use(repo, cpv)

    if len(matches) == 0:
        matches = find_single_use(repo, cpv)
    if len(matches) == 0:
        matches = find_python_compat(repo, cpv)

    return matches


def atom_maints(atom) -> list:
    # Get list of strings per maintainer object
    strings = [str(maint) for maint in atom.maintainers]

    # Slice off the name, get the <email>
    mails = [maint.split(" ")[-1] for maint in strings]

    # Return list of plain emails
    return [mail.replace("<", "").replace(">", "") for mail in mails]


def set_blocker(session, blocker, bug_id, apikey):
    params = {
        "Bugzilla_api_key": apikey,
        "id_or_alias": bug_id,
    }

    req = session.post(BZ_API.format(endpoint="bug"), params=params)


def file_stablereq(session, url, blocker, apikey, cpv):
    params = {
        "Bugzilla_api_key": apikey,

        "product": "Gentoo Linux",
        "component": "Stabilization",
        "version": "unspecified",
        "description": "Please stabilize.",
        "blocks": blocker,
        "url": url,
    }

    package = get_suitable_version(cpv)[0]
    package_str = str(package.versioned_atom).replace("=", "")
    params["cf_stabilisation_atoms"] = package_str + " *"

    if package.live:
        print("Can't file for live package: " + cpv)
        return

    maintainers = atom_maints(package)

    params["summary"] = package_str + \
        ": stabilization for python3_8"

    params["assigned_to"] = maintainers[0]

    if len(maintainers) > 1:
        params["cc"] = maintainers[1:]

    import pdb
    pdb.set_trace()

    req = session.post(BZ_API.format(endpoint="bug"), params=params)

    print(req.json()['id'])

    #set_blocker(session, blocker, req.json()["id"], apikey)
    # TODO: set_blocker is broken and it should add package list and leading =
    # isn't chopped off when filing


if __name__ == "__main__":
    session = requests.Session()
    params = {}
    bugzrc = os.path.expanduser("~/.bugzrc")

    if not os.path.isfile(bugzrc):
        print("Can't access {}".format(bugzrc))
        sys.exit(-1)

    config = ConfigParser()
    config.read(bugzrc)
    apikey = config['default']['key']

    packages = get_package_list("python3_7", "python3_8")

    for cpv in packages:
        if "heimdal" in cpv:
            continue
        pn = cpv.split(":")[0]
        slot = cpv.split(":")[-1]

        if slot != '0':
            print("Naively not processing nonzero slot: {}".format(cpv))
            continue

        bugs = find_stablereqs(session, pn)

        if len(bugs) == 0:
            file_stablereq(session,
                           "https://qa-reports.gentoo.org/output/gpyutils/37-to-38-stablereq.txt",
                           736709, apikey, pn)
            print("Need to file for {cpv}".format(cpv=cpv))
        else:
            # TODO: an improvement would be checking that bugs here are
            # actually stablereqs
            print("{cpv}: {bugs}".format(cpv=cpv, bugs=" ".join(
                                         [str(bug['id']) for bug in bugs])))

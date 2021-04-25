from configparser import ConfigParser
import os

import requests

import pkgcore.config
from pkgcore.ebuild import atom as atom_mod


BZ_BUG_API = "https://bugs.gentoo.org/rest/bug"


def get_api_key():
    bugzrc = os.path.expanduser("~/.bugzrc")
    config = ConfigParser()
    config.read(bugzrc)
    apikey = config['default']['key']
    return apikey


def cp_atom(atom_str):
    repo = pkgcore.config.load_config().repo['gentoo']
    atom = atom_mod.atom(atom_str)
    return repo.match(atom)


def atom_maints(atom) -> list:
    # Get list of strings per maintainer object
    strings = [str(maint) for maint in atom.maintainers]

    # Slice off the name, get the <email>
    mails = [maint.split(" ")[-1] for maint in strings]

    # Return list of plain emails
    mails = [mail.replace("<", "").replace(">", "") for mail in mails]

    if len(mails) > 0:
        return mails
    else:
        return ["maintainer-needed@gentoo.org"]


def file_bug(params):
    params["Bugzilla_api_key"] = get_api_key()
    params["version"] = "unspecified"

    return requests.post(BZ_BUG_API, data=params)

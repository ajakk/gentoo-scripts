#!/usr/bin/env python

from configparser import ConfigParser
from typing import List
import argparse
import json
import os
import subprocess
import sys

from pkgcore.ebuild import atom as atom_mod
import pkgcore.config
import requests


BZ_BUG_API = "https://bugs.gentoo.org/rest/bug"


def atom_maints(atom) -> list:
    # Get list of strings per maintainer object
    strings = [str(maint) for maint in atom.maintainers]

    # Slice off the name, get the <email>
    mails = [maint.split(" ")[-1] for maint in strings]

    # Return list of plain emails
    mails = [mail.replace("<", "").replace(">", "") for mail in mails]

    if len(mails) > 0:
        return mails
    return ["maintainer-needed@gentoo.org"]


def cp_atom(atom_str):
    repo = pkgcore.config.load_config().repo['gentoo']
    atom = atom_mod.atom(atom_str)
    return repo.match(atom)


def get_api_key():
    bugzrc = os.path.expanduser("~/.bugzrc")
    config = ConfigParser()
    config.read(bugzrc)
    apikey = config['default']['key']
    return apikey


def file_bug(params):
    params["Bugzilla_api_key"] = get_api_key()
    params["version"] = "unspecified"

    return requests.post(BZ_BUG_API, data=params)


def urldata(url):
    response = requests.get(url)
    if response.status_code != 200:
        print('{} status code for URL: {}'.format(response.status_code, url))
        print(response.content)
        sys.exit(1)
    return response.content


def get_ref_urls(data):
    refs = data['cve']['references']['reference_data']
    return [ref['url'] for ref in refs]


def generate_cve_description(cve_list):
    desc = []
    for data in cve_list:
        cve_id = data['cve']['CVE_data_meta']['ID']
        # So this description_data chunk of the JSON is something like:
        # {'description_data': [{'lang': 'en', 'value': 'FFmpeg 4.2 is affected by a Divide By Zero issue via libavcodec/aaccoder, which allows a remote malicious user to cause a Denial of Service'}]}
        # We use a magic '0' to index this array, but is it ever
        # bigger than one?
        cve_desc = data['cve']['description']['description_data'][0]['value']
        if len(data['cve']['description']['description_data']) > 1:
            print(cve_id + "\'s description array is bigger than one, take a look!")
            sys.exit(1)
        cve_refs = get_ref_urls(data)

        if len(cve_refs) > 0:
            desc.append("{} ({}):".format(cve_id, cve_refs[0]))
            if len(cve_refs) > 1:
                for ref in cve_refs[1:]:
                    desc.append("# {}".format(ref))
        else:
            desc.append("{}:".format(cve_id))
        desc.append("")
        desc.append(cve_desc)
        desc.append("")
    return '\n'.join(desc)


def write_edit_read(editor, string):
    path = "/tmp/secbug-file.txt"
    with open(path, "w") as f:
        f.write(string)
    subprocess.run([editor, path])
    with open(path, "r") as f:
        return f.read()


def get_editor():
    try:
        return os.environ['EDITOR']
    except KeyError:
        return 'nano'


def edit_data(package, cves, cve_list, cc):
    string = []

    if len(cves) > 1:
        # Would be nice to resolve e.g.
        # CVE-2018-1111,CVE-2020-2222,CVE-2020-3333 to
        # CVE-2018-1111,CVE-2020-{2222,3333}
        string.append("Summary: " + package + ": multiple vulnerabilities (")
    else:
        string.append("Summary: " + package + ": " + "(" + cves[0] + ")")

    string.append("CC: " + ','.join(cc))
    string.append("Alias: " + ','.join(cves))
    string.append("Whiteboard: ")
    string.append("URL: ")
    string.append("Description: " + generate_cve_description(cve_list))

    return write_edit_read(get_editor(), '\n'.join(string))


def get_cve_data(cves):
    cve_data = []
    base_url = 'https://services.nvd.nist.gov/rest/json/cve/1.0/'
    for cve in cves:
        cve_data.append(json.loads(urldata(base_url + cve))['result']['CVE_Items'][0])
    return cve_data


def _startswith_any(string: str, substrings: List[str]):
    for substr in substrings:
        if string.startswith(substr):
            return True
    return False


def resolve_severity(whiteboard):
    if "~" in whiteboard or whiteboard.startswith("C4"):
        return "trivial"
    elif _startswith_any(whiteboard, ["A4", "B3", "B4", "C3"]):
        return "minor"
    elif _startswith_any(whiteboard, ["A3", "B2", "C2"]):
        return "normal"
    elif _startswith_any(whiteboard, ["A2", "B1", "C1"]):
        return "major"
    elif _startswith_any(whiteboard, ["A1", "C0"]):
        return "critical"
    elif _startswith_any(whiteboard, ["A0", "B0"]):
        return "blocker"
    else:
        # TODO: error handling, probably should reopen editor for it
        return "normal"


def confirm():
    i = input("File bug? [yN] ")
    return 'y' in i.lower()


def file_bug_from_data(bugdata):
    params = {
        "product": "Gentoo Security",
        "component": "Vulnerabilities",
    }
    desc = []

    for line in bugdata.splitlines():
        # These magic numbers are the strings preceeding each line's data that
        # we don't care about
        if line.startswith("#"):
            continue
        elif line.startswith("Summary: "):
            params["summary"] = line[9:]
        elif line.startswith("CC"):
            params["cc"] = line[4:].split(',')
        elif line.startswith("Alias: "):
            if len(line) > 7:
                params["alias"] = line[7:]
        elif line.startswith("Whiteboard: "):
            if len(line) > 12:
                params["whiteboard"] = line[12:]
        elif line.startswith("URL: "):
            if len(line) > 5:
                params["url"] = line[5:]
        elif line.startswith("Description: "):
            if len(line) > 13:
                desc.append(line[13:])
        else:
            desc.append(line)

    params["description"] = '\n'.join(desc)
    if params["whiteboard"]:
        params["severity"] = resolve_severity(params["whiteboard"])
    bug = file_bug(params)
    try:
        print("Filed https://bugs.gentoo.org/{}".format(bug.json()['id']))
    except KeyError:
        print("Something went wrong filing the bug")
        import pdb; pdb.set_trace()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--cves', type=str, required=True, nargs='+')
    parser.add_argument('-p', '--package', type=str, required=True)
    args = parser.parse_args()

    cves = sorted(args.cves)
    cve_data = get_cve_data(cves)

    atom = cp_atom(args.package)[0]
    maints = atom_maints(atom)

    data = edit_data(args.package, cves, cve_data, maints)
    if not confirm():
        print("Not filing")
        sys.exit(0)
    file_bug_from_data(data)

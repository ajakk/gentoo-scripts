#!/usr/bin/env python

from configparser import ConfigParser
from typing import List
import argparse
import json
import os
import subprocess
import sys

from bugzilla import Bugzilla
from pkgcore.ebuild import atom as atom_mod
import pkgcore.config
import requests


def get_api_key():
    bugzrc = os.path.expanduser("~/.bugzrc")
    config = ConfigParser()
    config.read(bugzrc)
    apikey = config['default']['key']
    return apikey


BZ_BUG_API = "https://bugs.gentoo.org/rest/bug"
bgo = Bugzilla('https://bugs.gentoo.org', api_key=get_api_key(), force_rest=True)


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
    repo = pkgcore.config.load_config().objects.repo['gentoo']
    atom = atom_mod.atom(atom_str)
    return repo.match(atom)


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


def get_bug(bug):
    response = requests.get(BZ_BUG_API + 'rest/bug/' + str(bug))


def get_ref_urls(data):
    refs = data['references']['reference_data']
    return [ref['url'] for ref in refs]


def generate_description(cve_list):
    desc = []
    for data in cve_list:
        cve_id = data['CVE_data_meta']['ID']
        # So this description_data chunk of the JSON is something like:
        # {'description_data': [{'lang': 'en', 'value': 'FFmpeg 4.2 is affected by a Divide By Zero issue via libavcodec/aaccoder, which allows a remote malicious user to cause a Denial of Service'}]}
        # We use a magic '0' to index this array, but is it ever
        # bigger than one?
        cve_desc = data['description']['description_data'][0]['value']
        if len(data['description']['description_data']) > 1:
            print(cve_id + "\'s description array is bigger than one, take a look!")
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
    args = editor
    args.append(path)
    subprocess.run(args)
    with open(path, "r") as f:
        return f.read()


def get_editor():
    try:
        return os.environ['EDITOR'].split(' ')
    except KeyError:
        return ['nano']


def edit_data(package, cves, cc, cve_data=None, bug_data=None):
    string = []

    if bug_data:
        string.append("Summary: {}".format(bug_data.summary))
    elif len(cves) > 1:
        string.append("Summary: {}: multiple vulnerabilities".format(package))
    else:
        string.append("Summary: {}: ".format(package))

    string.append("CC: " + ','.join(cc))
    string.append("Alias: " + ','.join(cves))

    if bug_data:
        string.append("Whiteboard: " + bug_data.whiteboard)
        string.append("URL: " + bug_data.url)
    else:
        string.append("Whiteboard: ")
        string.append("URL: ")

    if cve_data:
        string.append("Description: {}".format(generate_description(cve_data)))
    else:
        string.append("Description: ")

    return write_edit_read(get_editor(), '\n'.join(string))


def get_cve_data(cves):
    cve_data = []
    base_url = 'https://services.nvd.nist.gov/rest/json/cve/1.0/'
    for cve in cves:
        year = cve.split('-')[1]
        num = cve.split('-')[2]

        if len(num) == 4:
            dirname = f"{num[0]}xxx"
        elif len(num) == 7:
            dirname = f"{num[:4]}xxx"
        else:
            dirname = f"{num[:2]}xxx"

        with open(os.path.expanduser(f"~/git/cvelist/{year}/{dirname}/{cve}.json")) as f:
            data = json.loads(f.read())

        cve_data.append(data)

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


def do_bug(bugdata, bug=None):
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
    if "whiteboard" in params:
        params["severity"] = resolve_severity(params["whiteboard"])

    if len(params["description"]) > 16384:
        print("Can't file if description is longer than 16384 characters!")

    if bug:
        # Hacky way to convert this from a bug creation to bug update
        # with a comment
        params['comment'] = {}
        params['comment']['body'] = params['description']
        del params['description']
        aliases = params['alias']
        params['alias'] = {}
        params['alias']['set'] = aliases.split(',')
        cc = params['cc']
        params['cc'] = {}
        params['cc']['add'] = cc
        bug = bgo.update_bugs([bug], params)
    else:
        bug = file_bug(params)
        try:
            print("Filed https://bugs.gentoo.org/{}".format(bug.json()['id']))
        except KeyError:
            print("Something went wrong filing the bug")
            import pdb; pdb.set_trace()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    op_types = parser.add_mutually_exclusive_group(required=True)
    op_types.add_argument('-b', '--bug', type=int, required=False)
    op_types.add_argument('-p', '--package', type=str, required=False)
    parser.add_argument('-c', '--cves', type=str, required=False, nargs='+')
    parser.add_argument('-n', '--nofetch', action='store_true', default=False)
    args = parser.parse_args()

    bug_data = None
    alias = []
    if args.bug:
        bug_data = bgo.getbug(args.bug)
        cc = bug_data.cc
        alias = bug_data.alias
    else:
        atoms = cp_atom(args.package)
        if len(atoms) < 1:
            print("Package {} doesn't seem to exist!".format(args.package))
            sys.exit(1)

        atom = atoms[0]
        cc = atom_maints(atom)

    if args.cves:
        alias = sorted(list(set(args.cves + alias)))

    if args.nofetch:
        data = edit_data(args.package, alias, cc)
    else:
        if args.cves:
            cve_data = get_cve_data(args.cves)
            data = edit_data(args.package, alias, cc, cve_data=cve_data, bug_data=bug_data)
        else:
            data = edit_data(args.package, alias, cc, bug_data=bug_data)

    if not confirm():
        print("Not filing")
        sys.exit(0)

    do_bug(data, args.bug)

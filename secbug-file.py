#!/usr/bin/env python

from typing import List
import argparse
import json
import os
import subprocess
import sys

import requests

import gbugs


def urldata(url):
    return requests.get(url).content


def decode_col(data, col):
    """
    Pandas encodes each column with the index in a format { col: {idx: data}},
    this function returns a column value out of this pattern
    """
    return list(data[col].values())[0]


def get_ref_urls(data):
    try:
        refs = decode_col(data, 'cve.references.reference_data')
        return [ref['url'] for ref in refs]
    except KeyError:
        return ""


def generate_cve_description(cve_list):
    desc = []
    for cve_data in [json.loads(data.decode()) for data in cve_list]:
        cve = decode_col(cve_data, 'cve.CVE_data_meta.ID')
        this_desc = decode_col(cve_data, 'value')
        refs = get_ref_urls(cve_data)

        if len(refs) > 0:
            desc.append("{} ({}):".format(cve, refs[0]))
            if len(refs) > 1:
                for ref in refs[1:]:
                    desc.append("# {}".format(ref))
        else:
            desc.append("{}:".format(cve))
        desc.append("")
        desc.append(this_desc)
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
    string.append("Description: " + generate_cve_description(cve_data))

    return write_edit_read(get_editor(), '\n'.join(string))


def get_cve_data(cves):
    cve_data = []
    for cve in cves:
        cve_data.append(urldata('http://127.0.0.1:8000/' + cve))
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
        return "badvalue"


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
    bug = gbugs.file_bug(params)
    try:
        print("Filed https://bugs.gentoo.org/{}".format(bug.json()['id']))
    except KeyError:
        import pdb; pdb.set_trace()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--cves', type=str, required=True, nargs='+')
    parser.add_argument('-p', '--package', type=str, required=True)
    args = parser.parse_args()

    cves = sorted(args.cves)
    cve_data = get_cve_data(cves)

    atom = gbugs.cp_atom(args.package)[0]
    maints = gbugs.atom_maints(atom)

    data = edit_data(args.package, cves, cve_data, maints)
    if not confirm():
        print("Not filing")
        sys.exit(0)
    file_bug_from_data(data)

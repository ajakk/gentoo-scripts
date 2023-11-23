#!/usr/bin/env python3

import sys

from gbugs import bgo


def main():
    if sys.stdin.isatty():
        aliases = sys.argv[1:]
    else:
        lines = sys.stdin.read()
        aliases = [line.strip() for line in lines.split()]

    if len(list(filter(None, aliases))) == 0:
        print("No input! Exiting")
        sys.exit(1)

    # deduplicate, sort
    aliases = sorted(list(set(aliases)))

    query = bgo.build_query(
        alias=aliases,
        include_fields=["id", "summary", "alias"],
    )

    bugs = bgo.query(query)

    for bug in bugs:
        for bug_alias in bug.alias:
            # keep track of the aliases we've seen so we can say which we
            # haven't seen at the end
            if bug_alias in aliases:
                aliases.remove(bug_alias)
        print(f"{bug.weburl} {bug.summary}")

    # if there are aliases we haven't seen, output them here
    if aliases:
        print(f"no bug: {' '.join(aliases)}")

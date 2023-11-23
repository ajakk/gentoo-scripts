#!/usr/bin/env python

import sys

from ajakscripts.gbugs import bgo


def all_done(bug):
    data = bgo.getbug(bug)
    update = {}

    new_whiteboard = data.whiteboard.replace("glsa", "glsa+")
    close = "[glsa+]" in new_whiteboard

    if close:
        update["status"] = "RESOLVED"
        update["resolution"] = "FIXED"
        update["comment"] = {"body": "GLSA released, all done!"}
    update["whiteboard"] = new_whiteboard

    print(f"[{data.id}]: {data.whiteboard} -> {new_whiteboard}" + (", closing" if close else ""))
    bgo.update_bugs([data.id], update)


def main():
    for bug in sys.argv[1:]:
        all_done(bug)


if __name__ == "__main__":
    main()

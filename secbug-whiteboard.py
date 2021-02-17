#!/usr/bin/python

# TODO
# More testing, then automatic updating of whiteboards
# Implement actual changes
# Clear stabilization keywords/package list/sanity check  when done stabling
# Comment 'Please cleanup' 'Please vote' etc
# Gets confused when stablization is finished while at 'stable?'

import argparse
import sys

import bugzilla

import gbugs

bz = bugzilla.Bugzilla('https://bugs.gentoo.org', api_key=gbugs.get_api_key())


def maybe_glsa(severity):
    return severity in ['blocker', 'critical', 'major', 'normal', 'minor']


def is_arch(email):
    arch_mails = ['amd64', 'arm', 'arm64', 'hppa', 'ppc', 'ppc64', 'sparc',
                  'x86', 's390']
    return email in map(lambda x: x + '@gentoo.org', arch_mails)


def is_sec_email(email):
    sec_mails = ['security', 'security-kernel', 'security-audit']
    return email in map(lambda x: x + '@gentoo.org', sec_mails)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-a', '--apply', action='store_true')
    parser.add_argument('bug', type=int)
    args = parser.parse_args()

    bug = bz.getbug(args.bug)

    update = {}

    # Go ahead and create an empty skeleton so we don't have to worry about
    # doing it on demand. Since it's empty, it shouldn't do anything anyway.
    update['keywords'] = {}
    update['keywords']['add'] = []
    update['keywords']['remove'] = []

    update['flag'] = {}

    # Basic sanity checks
    if not is_sec_email(bug.assigned_to):
        print("Not a security bug! Exiting.")
        sys.exit(-1)
    if len(bug.whiteboard) == 0:
        print("Bug has no whiteboard! Exiting.")
        sys.exit(-1)

    evaluation = bug.whiteboard[:2]
    wb_next = []

    if any(is_arch(email) for email in bug.cc):
        wb_next.append('stable')
        if 'CC-ARCHES' not in bug.keywords:
            update['keywords']['add'].append('CC-ARCHES')
        if 'STABLEREQ' not in bug.keywords:
            update['keywords']['add'].append('STABLEREQ')
    elif 'stable?' in bug.whiteboard:
        wb_next.append('stable?')

    done_stabling = 'stable' in bug.whiteboard and \
        not any(is_arch(email) for email in bug.cc)

    if done_stabling:
        #import pdb; pdb.set_trace()
        update['keywords']['remove'] = ['CC-ARCHES', 'STABLEREQ']
        update['cf_stabilisation_atoms'] = ''
        update['flag']['name'] = 'sanity-check'
        update['flag']['status'] = 'X'
        update['comment'] = 'Please cleanup'

    if 'glsa+' in bug.whiteboard:
        wb_next.append('glsa+')
    elif (bug.severity != 'trivial' and
          ('glsa?' in bug.whiteboard or 'ebuild' not in bug.whiteboard)) or \
         (done_stabling or 'cleanup' in bug.whiteboard):
        # If the severity isn't trivial, If glsa? was already there
        wb_next.append('glsa?')
    elif 'noglsa' in bug.whiteboard:
        wb_next.append('noglsa')
    elif 'glsa' in bug.whiteboard:
        wb_next.append('glsa')

    if done_stabling or 'cleanup' in bug.whiteboard:
        wb_next.append('cleanup')

    if 'cve' in bug.whiteboard:
        wb_next.append('cve')

    # Make sure the format is correct
    update['whiteboard'] = evaluation + ' [' + ' '.join(wb_next) + ']'

    print("Old whiteboard: " + bug.whiteboard)
    print("New dict: " + str(update))

    if args.apply:
        if 'y' in input("Update? [yN] "):
            bz.update_bugs([args.bug], update)

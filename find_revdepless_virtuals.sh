#!/usr/bin/env bash

revdeps() {
	# depindex is generated from the script here:
	# https://gitweb.gentoo.org/proj/qa-scripts.git/tree/genrdeps-index.py
	grep "" /var/lib/jake/gentoo/tooling/qa-scripts/depindex/*/"${1}"
}

path_to_catpkg() {
	echo "$(basename $(dirname ${1}))/$(basename ${1})"
}

for x in $(find /var/db/repos/gentoo/virtual -maxdepth 1 -mindepth 1 -type d); do
	pkg=$(path_to_catpkg "${x}")
	if [[ -z $(revdeps "${pkg}" 2>/dev/null) ]]; then
		echo "${pkg}"
	fi
done

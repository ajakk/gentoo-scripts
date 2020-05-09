#!/bin/bash

WD="$(dirname $0)/"

[[ -f $(which bugz) ]] || echo "Needs bugz"

search_reqs() {
	# Start with a basic search, grep for "stabili[sz]e" or "stable" in bug
	# title, grab out the bug number
	bugs=$(bugz --columns 9999 --quiet search "${1}" |
		grep -iE '(stabili[zs]e|stable)' |
		awk '{print $1}')

	echo ${bugs}
}

get_impls() {
	# We only care about the newest version
	impls=$(${WD}/get-python-impls.py $1 | tail -1 | sed 's/.*: //')

	echo ${impls}
}

main() {
	# Extra parens convert to array
	pkgs=($(curl --silent https://qa-reports.gentoo.org/output/gpyutils/${1}-stablereq.txt))

	for pkg in ${pkgs[@]}; do
		# Clean up the atom before searching
		pkg=$(qatom ${pkg} -F '%{CATEGORY}/%{P}')
		bugs=$(search_reqs ${pkg})

		if [[ -n $bugs ]]; then
			echo "${pkg},${bugs},$(get_impls $pkg)"
		else
			echo "${pkg},none,$(get_impls $pkg)"
		fi
	done
}

main $1

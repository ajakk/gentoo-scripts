#!/bin/bash

WD="$(dirname $0)/"

[[ -f $(which bugz) ]] || echo "Needs www-client/pybugz"
[[ -f $(which gpy-showimpls) ]] || echo "Needs app-portage/gpyutils"

search_reqs() {
	# Start with a basic search, grep for "stabili[sz]" or "stable" in bug
	# title, grab out the bug number
	bugs=$(bugz --columns 9999 --quiet search "${1}" |
		grep -iE '(stabili[zs]|stable)' |
		awk '{print $1}')

	echo ${bugs}
}

get_impls() {
	# We only care about the newest version
	impls=$(${WD}/get-python-impls.py $1 | tail -1 | sed 's/.*: //')

	echo ${impls}
}

output_req() {
	# Clean up the atom before searching
	pkg=$(qatom ${1} -F '%{CATEGORY}/%{P}')
	bugs=$(search_reqs ${pkg})

	if [[ -n $bugs ]]; then
		echo "${pkg},${bugs},$(get_impls $pkg)"
	else
		echo "${pkg},none,$(get_impls $pkg)"
	fi
}

while getopts ":f" o; do
	case "${o}" in
		f)
			f=1
			;;
	esac
done


if [[ $f ]]; then
	shift $((OPTIND-1))

	while read pkg; do
		output_req "${pkg}"
	done < "${1:-/dev/stdin}"
else
	for pkg in $@; do
		echo "checking ${pkg}"
		output_req "${pkg}"
	done
fi

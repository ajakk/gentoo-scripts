get_maints() {
	pkgs=$(curl --silent ${1})

	for pkg in $pkgs; do
		maint=$(pquery ${pkg} --one-attr maintainers | tail -1 | sed 's/.*"//;s/".*//')
		if [[ ${maint} ]]; then
			echo "$(qatom ${pkg} -F '%{CATEGORY}/%{P}'),${maint},${2}"
		else
			echo "$(qatom ${pkg} -F '%{CATEGORY}/%{P}'),maintainer-needed,${2}"
		fi
	done
}

get_maints https://qa-reports.gentoo.org/output/gpyutils/36-to-37.txt "36-to-37"
get_maints https://qa-reports.gentoo.org/output/gpyutils/37-to-38.txt "37-to-38"

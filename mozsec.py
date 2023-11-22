#!/usr/bin/env python

import sys
import requests

from bs4 import BeautifulSoup as bs


BASE = 'https://www.mozilla.org/'


def urldata(url):
    response = requests.get(url)
    if response.status_code != 200:
        print('{} status code for URL: {}'.format(response.status_code, url))
        print(response.content)
        sys.exit(1)
    return response.content


def is_firefox(soup):
    # Look for 'firefox' in the 'Products' field of the table just below the heading
    return 'Firefox' in soup.find_all('dl')[0].find_all('dt')[2].next.next.next.text


def is_tb(soup):
    return 'Thunderbird' in soup.find_all('dl')[0].find_all('dt')[2].next.next.next.text


def get_versions(soup):
    return soup.find_all('dl')[0].find_all('li')[0].text


def grok_cves(soup):
    return [header.find('a')['href'][1:]
            for header in soup.find_all('h4', {'class': 'level-heading'})]


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} offset")
        sys.exit(0)
    soup = bs(urldata(BASE + '/en-US/security/advisories/'), features='lxml')
    links = soup.find('article').find_all('ul')[int(sys.argv[1]) + 1].find_all('a')
    advisories = [a['href'] for a in links]
    soups = [bs(urldata(BASE + path), features='lxml') for path in advisories]

    ff_ver = []
    ff_cves = []
    tb_ver = []
    tb_cves = []

    for soup in soups:
        if is_firefox(soup):
            ff_ver += [get_versions(soup)]
            ff_cves += grok_cves(soup)
        elif is_tb(soup):
            tb_ver += [get_versions(soup)]
            tb_cves += grok_cves(soup)

    tracker_cves = set(ff_cves).intersection(set(tb_cves))

    if tracker_cves:
        print('Tracker CVEs: ' + ' '.join(tracker_cves))

    if ff_ver:
        print(' '.join(ff_ver))
        print(' '.join(sorted(set(ff_cves).difference(tracker_cves))))

    if tb_ver:
        print(' '.join(tb_ver))
        print(' '.join(sorted(set(tb_cves).difference(tracker_cves))))

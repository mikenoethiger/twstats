#!/usr/bin/python

import argparse
import sys
import re
import requests
import time
from html.parser import HTMLParser

class HTMLParserTagFilter(HTMLParser):
    """Extract all occurrences of a tag in an HTML string"""

    def __init__(self, tag):
        super().__init__()
        self.tag = tag
        self.occurrences = []
        self.occurrence = ''
        self.append = False

    def handle_starttag(self, tag, attrs):
        if tag == self.tag and not self.append:
            self.append = True
            self.occurrence = f'<{tag}>'
        elif self.append:
            self.occurrence += f'<{tag}>'

    def handle_endtag(self, tag):
        if tag == self.tag:
            self.occurrences.append(self.occurrence + f'</{tag}>')
            self.occurrence = ''
            self.append = False
        elif self.append:
            self.occurrence += f'</{tag}>'

    def handle_data(self, data):
        if self.append:
            self.occurrence += data


class ExtractHTMLData(HTMLParser):

    def __init__(self):
        super().__init__()
        self.data = []

    def handle_data(self, d):
        if len(d.strip()) > 0:
            self.data.append(d)

    def numbers(self):
        """Extract numbers from self.data"""
        num_strings = re.findall('[0-9]+', re.sub('[.,]', '', ''.join(self.data)))
        return [int(num) for num in num_strings]

    def clear_data(self):
        """Clear self.data"""
        self.data = []


def extract_numbers(html):
    parser = ExtractHTMLData()
    parser.feed(html)
    return parser.numbers()


def fetch_stats(url):
    """
    Fetch stats from url.
    Example URL: https://ch60.staemme.ch/page/stats

    Returns
    -------
    success: bool
        True, if stats were successfully fetched
    stats : dict
        Stats data (all values are 0 if not successful). Dict contains the following entries:
    {
        'n_players': int
        'total_villages': int
        'player_villages': int
        'barb_villages': int
        'bonus_villages': int
        'server_runtime': int
        'players_online': int
        'messages_sent': int
        'forum_posts': int
        'troop_movements': int
        'trade_movements': int
        'n_tribes': int
        'n_players_in_tribes': int
        'total_points': int
        'total_wood': int
        'total_clay': int
        'total_iron': int
        'spear': int
        'sword': int
        'axe': int
        'archer': int
        'scout': int
        'light': int
        'marcher': int
        'heavy': int
        'ram': int
        'cat': int
        'knight': int
        'noble': int
        'aggregated_at': str
    }
    """
    keys = ['n_players', 'total_villages', 'player_villages', 'barb_villages', 'bonus_villages', 'server_runtime',
            'players_online', 'messages_sent', 'forum_posts', 'troop_movements', 'trade_movements', 'n_tribes',
            'n_players_in_tribes', 'total_points', 'total_wood', 'total_clay', 'total_iron', 'spear', 'sword', 'axe',
            'archer', 'scout', 'light', 'marcher', 'heavy', 'ram', 'cat', 'knight', 'noble', 'aggregated_at']
    # create empty stats
    empty_stats = dict(zip(keys, [0]*len(keys)))
    stats = empty_stats.copy()
    res = requests.get(url)
    if not res:
        print(res.status_code, res.reason, 'failed to get', url, file=sys.stderr)
        return False, empty_stats

    table_html = re.findall('<table.*</table>', res.text)
    if len(table_html) != 1:
        print('expected to find 1 table but found', len(table_html), 'tables', file=sys.stderr)
        return False, empty_stats
    table_html = table_html[0]
    table_row_parser = HTMLParserTagFilter(tag='tr')
    table_row_parser.feed(table_html)
    rows = table_row_parser.occurrences
    if len(rows) < 20:
        print('expected to have at least 20 table rows but found', len(rows), 'rows', file=sys.stderr)
        return False, empty_stats
    # worlds with bonus villages have one additional row in stats table
    bonus = 1 if len(rows) > 20 else 0
    stats['n_players'] = extract_numbers(rows[0])[0]
    stats['total_villages'] = extract_numbers(rows[1])[0]
    stats['player_villages'] = extract_numbers(rows[2])[0]
    stats['barb_villages'] = extract_numbers(rows[3])[0]
    if bonus > 0:
        stats['bonus_villages'] = extract_numbers(rows[4])[0]
    try:
        # server run-time may say "Not started yet" if the world has not started yet, hence no number available
        stats['server_runtime'] = extract_numbers(rows[5+bonus])[0]
    except IndexError:
        stats['server_runtime'] = 0
    stats['players_online'] = extract_numbers(rows[6+bonus])[0]
    stats['messages_sent'] = extract_numbers(rows[7+bonus])[0]
    stats['forum_posts'] = extract_numbers(rows[8+bonus])[0]
    stats['troop_movements'] = extract_numbers(rows[9+bonus])[0]
    stats['trade_movements'] = extract_numbers(rows[10+bonus])[0]
    stats['n_tribes'] = extract_numbers(rows[11+bonus])[0]
    stats['n_players_in_tribes'] = extract_numbers(rows[12+bonus])[0]
    stats['total_points'] = extract_numbers(rows[13+bonus])[0]
    parser = HTMLParserTagFilter(tag='li')
    parser.feed(rows[14+bonus])
    stats['total_wood'] = extract_numbers(parser.occurrences[0])[0]
    stats['total_clay'] = extract_numbers(parser.occurrences[1])[0]
    stats['total_iron'] = extract_numbers(parser.occurrences[2])[0]
    units_parser = HTMLParserTagFilter(tag='li')
    units_parser.feed(rows[15 + bonus])
    n_units = len(units_parser.occurrences)
    troop_amounts = []
    for i in range(n_units):
        amount_parser = ExtractHTMLData()
        amount_parser.feed(units_parser.occurrences[i])
        amount = amount_parser.numbers()[0]
        # check if mio. or m appendix is present, which denotes numbers in millions
        if 'm' in ''.join(amount_parser.data).lower():
            amount *= 1_000_000
        troop_amounts.append(amount)
    # possible troop configs:
    # paladin archer marcher enabled_units
    # yes     yes    yes     12
    # no      yes    yes     11
    # yes     no     no      10
    # no      no     no      9
    if n_units == 12:
        order = ['spear', 'sword', 'axe', 'archer', 'scout', 'light', 'marcher', 'heavy',
                 'ram', 'cat', 'knight', 'noble']
    elif n_units == 11:
        order = ['spear', 'sword', 'axe', 'archer', 'scout', 'light', 'marcher', 'heavy',
                 'ram', 'cat', 'noble']
    elif n_units == 10:
        order = ['spear', 'sword', 'axe', 'scout', 'light', 'heavy', 'ram', 'cat', 'knight', 'noble']
    elif n_units == 9:
        order = ['spear', 'sword', 'axe', 'scout', 'light', 'heavy', 'ram', 'cat', 'noble']
    else:
        print(f'unknown units configuration with n_units={n_units}', file=sys.stderr)
        return False, empty_stats
    for i in range(n_units):
        stats[order[i]] = troop_amounts[i]

    stats['aggregated_at'] = re.findall('\d\d:\d\d', res.text)[0]

    return True, stats

# Erwünschtes Verhalten:
#   Beim starten des Programms werden die Statistiken einer Liste von Stämme servern heruntergeladen
#   Die Liste wird vom User angegeben
#

def print_usage():
    print('Usage: python %s [https://server1] [https://server2] [...] [file1.txt] [...]' % sys.argv[0])

    print('EXAMPLES')
    print('  Listing servers as program args:')
    print('    python %s https://ch.staemme.ch/page/stats https://de.die-staemme.de/page/stats' % sys.argv[0])
    print('  Listing servers in a file called servers.txt:')
    print('    python %s server.txt' % sys.argv[0])

    print('Example: ')


def resolve_urls(urls_or_files):
    """
    Resolves a list of strings to a list of URLs in the following way:
    A string which begins with https:// is already an URL
    Other strings are treated as files which contain an URL on every line.
    """
    urls = []
    for arg in urls_or_files:
        if arg.startswith('https://'):
            urls.append(arg)
        else:
            f = open(arg, 'r')
            stripped_lines = [l.strip() for l in f.readlines()]
            urls += filter(lambda l: len(l) > 0, stripped_lines)
    return urls


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Fetch stats of all active worlds from https://[tribalwars_domain]/page/stats'
                                                 ' and write to stdout in csv format. Log messages and errors are written to stderr.')
    parser.add_argument('urls_or_files', metavar='url|file', type=str, nargs='+',
                        help='tribalwars server URL or file containing one URL per line. Example URL: '
                             'https://staemme.ch')
    parser.add_argument('-c, --column-names', dest='column_names', const=True, action='store_const', default=False,
                        help='first line written to stdout is the name of columns')
    args = parser.parse_args()

    base_urls = resolve_urls(args.urls_or_files)

    iteration = 0
    for base_url in base_urls:
        stats_url = base_url + '/page/stats'
        try:
            res = requests.get(stats_url)
        except requests.exceptions.RequestException:
            print('failed to connect to', stats_url, file=sys.stderr)
            continue

        if not res:
            print(res.status_code, res.reason, 'for', stats_url, file=sys.stderr)
            continue

        # get unique list of worlds
        world_urls = list(set(re.findall('https://[a-zA-Z0-9\./-]*/page/stats', res.text)))
        for url in world_urls:
            world = url.split('.')[0][8:]
            success, stats = fetch_stats(url)
            if success:
                print('fetched stats for', url, file=sys.stderr)
            else:
                print('failed to fetch stats for', url, file=sys.stderr)
                continue

            header = ['world', 'fetch_timestamp'] + list(stats.keys())
            values = [world, int(time.time())] + list(stats.values())
            if iteration == 0 and args.column_names:
                print(','.join(header))
            print(','.join(list(map(str, values))))
            iteration += 1

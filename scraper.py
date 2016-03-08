import re
from urlparse import urljoin
from urllib import quote

from HTMLParser import HTMLParser
unescape = HTMLParser().unescape

import requests
import lxml.html

import execjs

source_url_base = 'http://parliament.gov.to/members-of-parliament/'
sources = (
    'peoples',
    'nobles',
    # 'ministers',
    )

request_headers = {'User-agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; Trident/7.0; AS; rv:11.0) like Gecko'}

data = []

people_re = re.compile(ur"People['\u2019]s Representative for (.*)")
noble_re = re.compile(ur"Noble(['\u2019]s|s['\u2019]) (?:No. ?(\d+) ?)?Representative for (.*)")


legislatures_data = [
    {'id': 2015, 'name': '2015-2018', 'start_date': 2015, 'end_date': 2018},
    ]


def unjs_email(script):
    """Takes a javascript email mangling script and returns the email address."""

    # Get hold of the lines of javascript which aren't fiddling with the DOM
    jslines = [x.strip() for x in re.search(r'<!--(.*)//-->', script, re.M | re.S).group(1).strip().splitlines() if not x.strip().startswith('document')]

    # The name of the variable containing the variable containing the email address
    # varies, so find it by regex.
    varname = re.search(r'var (addy\d+)', script).group(1)
    jslines.append('return {}'.format(varname))

    js = '(function() {{{}}})()'.format(' '.join(jslines))

    return unescape(execjs.eval(js))


for source in sources:
    source_url = urljoin(source_url_base, source)
    resp = requests.get(source_url, headers=request_headers)
    root = lxml.html.fromstring(resp.text)

    for item in root.cssselect('.item'):
        member = {
            'party': '',  # No party information on the official site
            'term_id': 2015,
            }
        name_a = item.cssselect("[itemprop='name'] a")[0]
        member['name'] = name_a.text.strip()
        details_url = member['details_url'] = urljoin(source_url, name_a.get('href'))

        member['id'] = details_url.rsplit('/', 1)[1]

        img = item.cssselect('img')
        if img:
            member['image'] = urljoin(source_url, quote(img[0].get('src')))

        member_resp = requests.get(details_url, headers=request_headers)
        member_root = lxml.html.fromstring(member_resp.text)

        data.append(member)

        details_table = None
        try:
            details_table = member_root.cssselect('table')[0]
        except:
            print "No details table for {}".format(member['name'])
            continue

        try:
            constituency_text = details_table.xpath("//tr/td[strong[contains(., 'Constituency')]]/following::td")[0].text_content()
        except IndexError:
            constituency_text = details_table.xpath("//tr/td[contains(., 'Constituency')]/following::td")[0].text_content()
        
        constituency_text = re.sub('\s+', ' ', constituency_text, flags=re.UNICODE)

        people_match = people_re.match(constituency_text) 
        noble_match = noble_re.match(constituency_text) 
        if people_match:
            member['constituency'] = people_match.group(1)
        elif noble_match:
            member['constituency'] = noble_match.group(2)
        else:
            print "No constituency found"
            import pdb;pdb.set_trace()

        try:
            script = details_table.xpath("//tr/td[strong[contains(., 'Email')]]")[0].find('script').text_content()
        except (AttributeError, IndexError):
            # No no email for this person.
            script = None
        else:
            member['email'] = unjs_email(script)

        try:
            member['cell'] = details_table.xpath("//tr/td[strong[contains(., 'Mobile Phone')]]")[0].text_content().split(':')[1].strip()
        except (IndexError, AttributeError):
            pass

        try:
            member['phone'] = details_table.xpath("//tr/td[strong[contains(., 'Home Phone')]]")[0].text_content().split(':')[1].strip()
        except (IndexError, AttributeError):
            pass

##########################################################################################
# Actually saving the data is down here to help me add and remove it repeatedly with Git #
##########################################################################################

import scraperwiki
scraperwiki.sqlite.save(unique_keys=['name', 'term_id'], data=data)
scraperwiki.sqlite.save(unique_keys=['id'], data=legislatures_data, table_name='terms')

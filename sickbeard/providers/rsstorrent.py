# Author: Mr_Orange
#
# This file is part of SickRage.
#
# SickRage is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# SickRage is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with SickRage.  If not, see <http://www.gnu.org/licenses/>.

import os
import re

import sickbeard
import generic

from sickbeard import helpers
from sickbeard import logger
from sickbeard import tvcache
from sickrage.helper.encoding import ek
from sickrage.helper.exceptions import ex

import requests
from bencode import bdecode


class TorrentRssProvider(generic.TorrentProvider):
    def __init__(self, name, url, cookies='', titleTAG='title', search_mode='eponly', search_fallback=False, enable_daily=False,
                 enable_backlog=False):
        generic.TorrentProvider.__init__(self, name)
        self.cache = TorrentRssCache(self)

        self.urls = {'base_url': re.sub('\/$', '', url)}

        self.url = self.urls['base_url']

        self.enabled = True
        self.ratio = None
        self.supportsBacklog = False

        self.search_mode = search_mode
        self.search_fallback = search_fallback
        self.enable_daily = enable_daily
        self.enable_backlog = enable_backlog
        self.cookies = cookies
        self.titleTAG = titleTAG

    def configStr(self):
        return "%s|%s|%s|%s|%d|%s|%d|%d|%d" % (self.name or '',
                                            self.url or '',
                                            self.cookies or '',
                                            self.titleTAG or '',
                                            self.enabled,
                                            self.search_mode or '',
                                            self.search_fallback,
                                            self.enable_daily,
                                            self.enable_backlog)

    def imageName(self):
        if ek(os.path.isfile,
                 ek(os.path.join, sickbeard.PROG_DIR, 'gui', sickbeard.GUI_NAME, 'images', 'providers',
                       self.getID() + '.png')):
            return self.getID() + '.png'
        return 'torrentrss.png'

    def isEnabled(self):
        return self.enabled

    def _get_title_and_url(self, item):

        title = item.get(self.titleTAG)
        if title:
            title = self._clean_title_from_provider(title)

        attempt_list = [lambda: item.get('torrent_magneturi'),

                        lambda: item.enclosures[0].href,

                        lambda: item.get('link')]

        url = None
        for cur_attempt in attempt_list:
            try:
                url = cur_attempt()
            except:
                continue

            if title and url:
                break

        return title, url

    def validateRSS(self):

        try:
            if self.cookies:
                cookie_validator = re.compile("^(\w+=\w+)(;\w+=\w+)*$")
                if not cookie_validator.match(self.cookies):
                    return (False, 'Cookie is not correctly formatted: ' + self.cookies)

            data = self.cache._getRSSData()['entries']
            if not data:
                return (False, 'No items found in the RSS feed ' + self.url)

            (title, url) = self._get_title_and_url(data[0])

            if not title:
                return (False, 'Unable to get title from first item')

            if not url:
                return (False, 'Unable to get torrent url from first item')

            if url.startswith('magnet:') and re.search('urn:btih:([\w]{32,40})', url):
                return (True, 'RSS feed Parsed correctly')
            else:
                if self.cookies:
                    requests.utils.add_dict_to_cookiejar(self.session.cookies,
                                                         dict(x.rsplit('=', 1) for x in (self.cookies.split(';'))))
                torrent_file = self.getURL(url)
                try:
                    bdecode(torrent_file)
                except Exception, e:
                    self.dumpHTML(torrent_file)
                    return (False, 'Torrent link is not a valid torrent file: ' + ex(e))

            return (True, 'RSS feed Parsed correctly')

        except Exception, e:
            return (False, 'Error when trying to load RSS: ' + ex(e))

    def dumpHTML(self, data):
        dumpName = ek(os.path.join, sickbeard.CACHE_DIR, 'custom_torrent.html')

        try:
            fileOut = open(dumpName, 'wb')
            fileOut.write(data)
            fileOut.close()
            helpers.chmodAsParent(dumpName)
        except IOError, e:
            logger.log("Unable to save the file: " + ex(e), logger.ERROR)
            return False
        logger.log(u"Saved custom_torrent html dump " + dumpName + " ", logger.INFO)
        return True

    def seedRatio(self):
        return self.ratio


class TorrentRssCache(tvcache.TVCache):
    def __init__(self, provider):
        tvcache.TVCache.__init__(self, provider)
        self.minTime = 15

    def _getRSSData(self):
        logger.log(u"TorrentRssCache cache update URL: " + self.provider.url, logger.DEBUG)

        if self.provider.cookies:
            self.provider.headers.update({'Cookie': self.provider.cookies})

        return self.getRSSFeed(self.provider.url)

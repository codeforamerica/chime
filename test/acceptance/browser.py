import re

__author__ = 'william'

FIREFOX_LATEST = ["35.0"]
CHROME_LATEST = ["39.0"]

ALL_BROWSERS = {
    "Windows": {
        "7": {
            "IE": ["8.0", "9.0", "10.0", "11.0"],
            "Firefox": FIREFOX_LATEST,
            "Chrome": CHROME_LATEST
        },
        "8.1": {
            "IE": ["11.0"],
            "Firefox": FIREFOX_LATEST,
            "Chrome": CHROME_LATEST
        }
    }

}


def _digits(string):
    results = re.findall(r'[.0-9]+', string)
    if results:
        return results[0]
    else:
        pass


class Browser:
    @staticmethod
    def all_browsers():
        result = []
        for os in ALL_BROWSERS:
            for os_version in ALL_BROWSERS[os]:
                for browser in ALL_BROWSERS[os][os_version]:
                    for browser_version in ALL_BROWSERS[os][os_version][browser]:
                        result.append(Browser(os, os_version, browser, browser_version))
        return result

    @staticmethod
    def _filter_for(string):
        if "/" in string:
            lumps = string.split('/')
            partials = [Browser._filter_for(lump) for lump in lumps]
            return lambda browser: reduce(lambda x, y: x and y(browser), partials, True)

        string = string.lower()
        items = []
        if string.startswith('ie'):
            items.append(lambda b: b.browser == 'IE')
            version = _digits(string)
            if version:
                items.append(lambda b: b.browser_version == version + '.0')
        elif string.startswith('win'):
            items.append(lambda b: b.os == 'Windows')
            version = _digits(string)
            if version:
                items.append(lambda b: b.os_version == version)
        else:
            raise ValueError('Unknown browser description "{}"'.format(string))

        return lambda b: reduce(lambda x, y: x and y(b), items, True)

    @staticmethod
    def from_string(string):
        if not string:
            return None
        if string == 'all':
            return Browser.all_browsers()
        elif string == 'supported':
            result = Browser.all_browsers()
            result.remove(Browser('Windows', '8.1', "IE", "11.0")) # currently disabling due to a strange test issue
            return result
        else:
            chosen_filter = Browser._filter_for(string)
            return [b for b in (Browser.all_browsers()) if chosen_filter(b)]

    def __init__(self, os, os_version, browser, browser_version):
        self.os = os
        self.os_version = os_version
        self.browser = browser
        self.browser_version = browser_version

    def as_browserstack_capabilities(self, other_info=None):
        result = other_info or {}
        result = result.copy()
        result.update({'os': self.os, 'os_version': self.os_version, 'browser': self.browser,
                       'browser_version': self.browser_version})
        return result

    def as_saucelabs_capabilities(self, other_info=None):
        result = other_info or {}
        result = result.copy()
        if self.browser == 'IE':
            browser_name = 'internet explorer'
        elif self.browser == 'Chrome':
            browser_name = 'chrome'
        elif self.browser == 'Firefox':
            browser_name = 'firefox'
        else:
            raise ValueError

        result.update({'platform': self.os + " " + self.os_version, 'browserName': browser_name,
                       'version': self.browser_version})
        return result

    def safe_name(self):
        return '_'.join([self._safe_text(n) for n in self._interesting_fields()])

    def _interesting_fields(self):
        return [self.os, self.os_version, self.browser, self.browser_version]

    @staticmethod
    def _safe_text(text):
        return re.sub('\W', '', re.sub('[.]', '_', text.lower()))

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.__dict__ == other.__dict__
        return False

    def __str__(self):
        return " ".join(self._interesting_fields())

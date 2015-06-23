import re

__author__ = 'william'

FIREFOX_LATEST = ["35.0"]
CHROME_LATEST = ["39.0"]

ALL_SUPPORTED = {
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

class Browser:
    @staticmethod
    def all_supported():
        result = []
        for os in ALL_SUPPORTED:
            for os_version in ALL_SUPPORTED[os]:
                for browser in ALL_SUPPORTED[os][os_version]:
                    for browser_version in ALL_SUPPORTED[os][os_version][browser]:
                        result.append(Browser(os, os_version, browser, browser_version))
        return result

    @staticmethod
    def from_string(string):
        all = Browser.all_supported()
        if string == 'all':
            return all
        if string == 'ie8':
            return [b for b in all if b.browser == 'IE' and b.browser_version == '8.0']

    def __init__(self, os, os_version, browser, browser_version):
        self.os = os
        self.os_version = os_version
        self.browser = browser
        self.browser_version = browser_version

    def as_selenium_capabilities(self,other_info=None):
        result = other_info or {}
        result = result.copy()
        result.update({'os': self.os, 'os_version': self.os_version, 'browser': self.browser,
                                'browser_version': self.browser_version})
        return result

    def safe_name(self):
        return '_'.join([self._safe_text(n) for n in self._interesting_fields()])

    def _interesting_fields(self):
        return [self.os, self.os_version, self.browser, self.browser_version]

    def _safe_text(self,text):
        return re.sub('\W', '', re.sub('[.]', '_', text.lower()))

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.__dict__ == other.__dict__
        return False

    def __str__(self):
        return " ".join(self._interesting_fields())



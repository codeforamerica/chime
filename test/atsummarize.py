import sys
import untangle
import ast
from collections import defaultdict

# Summarizes chime acceptance test output. Files generated with something like
# while true; do env TESTING_EMAIL=william+persona.org+autotest@codeforamerica.org
#     TESTING_PASSWORD=n7CGQgmn nosetests --with-xunit
#     --xunit-file=nt-`date +%Y%m%d-%H%M%S`.xml test/acceptance/; sleep 1; done

class Stats:
    records = []

    def record(self, *args, **data):
        data['browsername'] = "{os}/{os_version} {browser}/{browser_version}".format(**data)
        self.records.append(data)

    def success_ratio_by_browser(self):
        success_by_browser = defaultdict(int)
        failure_by_browser = defaultdict(int)

        for record in self.records:
            if record['success']:
                success_by_browser[record['browsername']] += 1
            else:
                failure_by_browser[record['browsername']] += 1

        keys = set(success_by_browser.keys()).union(set(failure_by_browser.keys()))
        result = {}
        for key in keys:
            success = success_by_browser[key]
            failure = failure_by_browser[key]
            result[key] = float(success) / (success + failure)
        return result

    def select(self, proc):
        return [i for i in self.records if proc(i)]


    def errors(self):
        return self.select(lambda d: d.has_key('error_type'))

    def failure_count(self):
        failures = defaultdict(int)
        for record in self.errors():
            failures[record['error_type']] += 1
        return failures


def load_stats(files):
    stats = Stats()
    for filename in files:
        try:
            results = untangle.parse(filename)
            for case in results.testsuite.testcase:

                params = ast.literal_eval(case.system_err.cdata.replace('Now testing on ', ''))
                if hasattr(case, 'error'):
                    params['error_type'] = case.error['type']
                stats.record(filename=filename,
                             time=case['time'],
                             success=(not (hasattr(case, 'error') or hasattr(case, 'failure'))),
                             **params)

        except Exception as e:
            print "skipping {} because {}".format(filename, e)
    return stats


stats = load_stats(sys.argv[1:])

print "Success ratio by browser:"
by_browser = stats.success_ratio_by_browser()
for key in by_browser.keys():
    print "  {key:<25} {value:2.2%}".format(key=key, value=by_browser[key])

print

print "test failure count:"
failures = stats.failure_count()
keys = failures.keys()
keys.sort(key=lambda x: -failures[x])
for key in keys:
    print "  {key:<25} {value:>3}".format(key=key, value=failures[key])
    for record in stats.select(lambda x:x['success']==False and x['error_type']==key):
        print "    {filename}".format(**record)

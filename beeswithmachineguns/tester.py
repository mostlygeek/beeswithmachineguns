"""
"""

from collections import namedtuple
import logging
import re



class Tester(object):
    """
    Abstract base class for tester implementations. 
    """

    def get_command(self, num_requests, concurrent_requests, is_keepalive, url):
        """
        Generate a command line to run a test using this tester.
        
        @param num_requests: number of requests this tester should issue
        @type num_requests: int
        @param concurrent_requests:  how many requests to issue at a time
        @type concurrent_requests: int
        @param is_keepalive: whether to use http keepalive
        @type is_keepalive: boolean
        @param url: the url to issue requests to
        @type url: str
        @return: the assembled command line
        @rtype: str
        """
        raise NotImplementedError
        

    def parse_output(self, output):
        """
        Create a L{TesterResult} by extracting values from the output of the tester
        command.
        
        This method will return None if the supplied output does not contain 
        sufficient data to generate a meaningful result.
        
        @param output: the captured output (stdout) from the tester command
        @type output: str
        @return: L{TesterResult} with the extracted data, or None
        """
        raise NotImplementedError


    def _parse_measure(self, expression, content, default=''):
        """
        Regular expression scraping helper
        
        @param expression: regular expression
        @param content: the output to scrape
        @param default: if the expression doesn't capture anything, return this
        """
        s = re.search(expression, content)
        return (s is not None and s.group(1)) or default
        
        
_result_keys = [
    'concurrency'
  , 'time_taken'
  , 'complete_requests'
  , 'failed_requests'
  , 'non_2xx_responses'
  , 'total_transferred'
  , 'requests_per_second'
  , 'ms_per_request'
  , 'pctile_50'
  , 'pctile_75'
  , 'pctile_90'
  , 'pctile_95'
  , 'pctile_99'
]

class TesterResult(namedtuple('TesterResult', _result_keys)):
    """
    Test result container, which works for both individual and aggregated
    results.  The individual fields map directly to ab results.  All values 
    are stored as floats.
    """
    
    def print_text(self, out):
        """
        Print summarized load-testing result to console.
        
        @param out: file-like, open for writing, into which output will be printed.
        """
    
        print >> out, 'Concurrency Level:\t%i' % self.concurrency
        print >> out, 'Complete requests:\t%i' % self.complete_requests
        print >> out, 'Failed requests:\t%i' % self.failed_requests
        print >> out, 'Non-2xx responses:\t%i' % self.non_2xx_responses
        print >> out, 'Total Transferred:\t%i bytes' % self.total_transferred
        print >> out, 'Requests per second:\t%.2f [#/sec] (mean)' % self.requests_per_second
        print >> out, 'Time per request:\t%.3f [ms] (mean)' % self.ms_per_request
        print >> out, '50%% response time:\t%i [ms] (mean)' % self.pctile_50
        print >> out, '75%% response time:\t%i [ms] (mean)' % self.pctile_75
        print >> out, '90%% response time:\t%i [ms] (mean)' % self.pctile_90
        print >> out, '95%% response time:\t%i [ms] (mean)' % self.pctile_95
        print >> out, '99%% response time:\t%i [ms] (mean)' % self.pctile_99
    

def get_aggregate_result(results):
    """
    Given a sequence of TestResults, generate a single aggregate TestResult.
    """
    
    ar = {}
    
    for k in _result_keys:        
        if k=='ms_per_request' or k.startswith('pctile'):
            # weighted mean.
            ar[k] = sum([(getattr(r,k) * r.complete_requests) for r in results]) /  sum([r.complete_requests for r in results])
            continue
        elif k=='time_taken':
            # time taken using max instead of sum...not precise.  
            # do not use in further aggregation.
            func = max
        else:
            # everything else is just summed
            func = sum
        ar[k] = func([getattr(r,k) for r in results])
    
    return TesterResult(**ar)


class ABTester(Tester):
    """
    Tester implementation for ab (apache benchmarking tool).
    """


    def get_command(self, num_requests, concurrent_requests, is_keepalive, url):
        """
        """
        cmd = []
        cmd.append('ab')
        cmd.append('-r')
        cmd.append('-n %s' % num_requests)
        cmd.append('-c %s' % concurrent_requests)

        if is_keepalive:
            cmd.append('-k')

        cmd.append('"%s"' % url)

        cmd_line = ' '.join(cmd)
        return cmd_line
        

    def parse_output(self, output):
        """
        """
        trd = {}        
        m = self._parse_measure

        trd['ms_per_request'] = \
            float(m('Time\ per\ request:\s+([0-9.]+)\ \[ms\]\ \(mean\)', output))

        if not trd['ms_per_request']:
            # problem with results...return None
            return None
        
        trd['concurrency'] = \
            float(m('Concurrency\ Level:\s+([0-9]+)', output))

        trd['requests_per_second'] = \
            float(m('Requests\ per\ second:\s+([0-9.]+)\ \[#\/sec\]\ \(mean\)', output))

        trd['time_taken'] = \
            float(m('Time\ taken\ for\ tests:\s+([0-9.]+)\ seconds', output))

        for pctile in (50, 75, 90, 95, 99):
            trd['pctile_%s' % pctile] = \
                float(m('\s+%s\%%\s+([0-9]+)' % pctile, output)) # e.g. '\s+50\%\s+([0-9]+)'

        trd['complete_requests'] = \
            float(m('Complete\ requests:\s+([0-9]+)', output))

        trd['failed_requests'] = \
            float(m('Failed\ requests:\s+([0-9]+)', output))

        # note - may not be present - default to 0
        trd['non_2xx_responses'] = \
            float(m('Non-2xx\ responses:\s+([0-9]+)', output, 0))

        trd['total_transferred'] = \
            float(m('Total\ transferred:\s+([0-9]+)', output))

        return TesterResult(**trd)


class SiegeTester(Tester):
    """
    """


    def get_command(self, num_requests, concurrent_requests, is_keepalive, url):
        """
        is_keepalive is currently ignored here, you instead have to specify
        it in 'bees up'.
        """
        
        cmd = []
        cmd.append('siege')
        cmd.append('-v')
        cmd.append('-i')
        cmd.append('-b')
        # siege multiplies the number of reqs you want by the concurrency,
        # which is different from how ab works, so we divide them pre-emptively
        cmd.append('-r %s' % max(1, (num_requests / concurrent_requests)))
        cmd.append('-c %s' % concurrent_requests)

        if url:
            cmd.append('"%s"' % url)
        else:
            cmd.append('-f urls.txt')

        cmd_line = ' '.join(cmd) + ' | siege_calc'
        return cmd_line


    def parse_output(self, output):
        """
        """
        trd = {}        
        m = self._parse_measure

        rt_secs = m('Response\ time:\s+([0-9.]+)\ secs', output)

        # give up now if we couldnt find the data
        if not rt_secs: return None

        trd['ms_per_request'] = \
            float(float(rt_secs) * 1000.0)

        trd['concurrency'] = \
            float(m('Concurrency:\s+([0-9.]+)', output))

        trd['requests_per_second'] = \
            float(m('Transaction rate:\s+([0-9.]+)\ trans/sec', output))

        trd['time_taken'] = \
            float(m('Elapsed\ time:\s+([0-9.]+)\ secs', output))

        # this bit requires siege_calc to be available on the worker bees
        for pctile in (50, 75, 90, 95, 99):
            trd['pctile_%s' % pctile] = \
                float(m('\s+%s\%%\s+([0-9]+)' % pctile, output, 0)) # e.g. '\s+50\%\s+([0-9]+)'

        trd['complete_requests'] = \
            float(m('Transactions:\s+([0-9]+)\ hits', output))

        trd['failed_requests'] = \
            float(m('Failed\ transactions:\s+([0-9]+)', output))

        # note - may not be present - default to 0
        # this isnt implemented yet either
        trd['non_2xx_responses'] = 0.0

        xferred_mb = m('Data\ transferred:\s+([0-9.]+) MB', output)
        trd['total_transferred'] = \
            float(float(xferred_mb) * 1024.0 * 1024.0)

        return TesterResult(**trd)

            

if __name__=='__main__':
    import sys
    SiegeTester().parse_timings(sys.stdin)
    

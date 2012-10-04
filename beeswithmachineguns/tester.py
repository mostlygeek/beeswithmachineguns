"""
"""

from collections import namedtuple
import logging
import re



class Tester(object):
    """
    """
    pass


_result_keys = [
    'concurrency'
  , 'time_taken'
  , 'complete_requests'
  , 'failed_requests'
  , 'non_2xx_responses'
  , 'total_transferred'
  , 'requests_per_second'
  , 'ms_per_request'
  , 'fifty_percent'
  , 'ninety_percent'
]

class TesterResult(namedtuple('TesterResult', _result_keys)):
    """
    """
    
    def print_text(self, out):
        """
        Print summarized load-testing result to console.
        """
    
        print >> out, 'Concurrency Level:\t%i' % self.concurrency
        print >> out, 'Complete requests:\t%i' % self.complete_requests
        print >> out, 'Failed requests:\t%i' % self.failed_requests
        print >> out, 'Non-2xx responses:\t%i' % self.non_2xx_responses
        print >> out, 'Total Transferred:\t%i bytes' % self.total_transferred
        print >> out, 'Requests per second:\t%f [#/sec] (mean)' % self.requests_per_second
        print >> out, 'Time per request:\t%f [ms] (mean)' % self.ms_per_request
        print >> out, '50%% response time:\t%f [ms] (mean)' % self.fifty_percent
        print >> out, '90%% response time:\t%f [ms] (mean)' % self.ninety_percent
    

def get_aggregate_result(results):
    """
    """
    
    ar = {}
    
    ar['concurrency']         = sum([r.concurrency for r in results])
    # time taken using max instead of sum...not precise.  do not use in further aggregation.
    ar['time_taken']          = max([r.time_taken for r in results])
    ar['complete_requests']   = sum([r.complete_requests for r in results])
    ar['failed_requests']     = sum([r.failed_requests for r in results])
    ar['non_2xx_responses']   = sum([r.non_2xx_responses for r in results])
    ar['total_transferred']   = sum([r.total_transferred for r in results])
    ar['requests_per_second'] = sum([r.requests_per_second for r in results])
    ar['ms_per_request']      = sum([r.ms_per_request for r in results]) / len(results)
    ar['fifty_percent']       = sum([r.fifty_percent for r in results]) / len(results)
    ar['ninety_percent']      = sum([r.ninety_percent for r in results]) / len(results)
    
    return TesterResult(**ar)


class ABTester(Tester):
    """
    Tester implementation for ab (apache benchmarking tool)
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
        

    def _parse_measure(self, expression, content, default=''):
        """
        """
        s = re.search(expression, content)
        return (s is not None and s.group(1)) or default
        
        
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

        trd['fifty_percent'] = \
            float(m('\s+50\%\s+([0-9]+)', output))

        trd['ninety_percent'] = \
            float(m('\s+90\%\s+([0-9]+)', output))

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


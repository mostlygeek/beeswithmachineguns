"""
"""
import os
import unittest

from beeswithmachineguns import tester 


class SiegeTesterTestCase(unittest.TestCase):
    """
    """
    
    def test_get_command(self):
        """
        """
        t = tester.SiegeTester()

        self.assertRaises(
                NotImplementedError
              , t.get_command
              , 3, 6, False, 'http://www.example.com/'
              )

        # This looks weird but is intentional:
        # number of requests should be divided across the concurrency.
        # since siege multiplies requests by concurrency, the tester 
        # divides the reps pre-emptively to achieve the desired number  
        self.assertEqual(
            "siege -i -b -r 10 -c 10 \"http://www.example.com/\" > /dev/null", 
            t.get_command(100, 10, True, 'http://www.example.com/')
            )


    def test_parse_output(self):
        """
        """
        def read_file(name):
            return open(os.path.join(os.path.dirname(__file__), name),'rb').read()
        
        t = tester.SiegeTester()
        
        self.assertEqual(
            tester.TesterResult(
                concurrency=0.04 # FIXME calculated differently from AB?
              , time_taken=59.22
              , complete_requests=1719.0
              , failed_requests=0.0
              , non_2xx_responses=0.0 # FIXME is this gonna work in siege?
              , total_transferred=7423918.08
              , requests_per_second=29.03
              , ms_per_request=0.0 # weird
              , pctile_50=0.0 # FIXME
              , pctile_75=0.0 # FIXME
              , pctile_90=0.0 # FIXME
              , pctile_95=0.0 # FIXME
              , pctile_99=0.0 # FIXME
              ),
            t.parse_output(read_file('siege-output-1.txt'))
            )
                
        self.assertEqual(
            tester.TesterResult(
                concurrency=47.12
              , time_taken=3.65
              , complete_requests=10000.0
              , failed_requests=0.0
              , non_2xx_responses=0.0
              , total_transferred=639631.36
              , requests_per_second=2739.73
              , ms_per_request=20.0
              , pctile_50=0.0 # FIXME
              , pctile_75=0.0 # FIXME
              , pctile_90=0.0 # FIXME
              , pctile_95=0.0 # FIXME
              , pctile_99=0.0 # FIXME
              ),
            t.parse_output(read_file('siege-output-2.txt'))
            )
                

if __name__=='__main__':
    unittest.main()


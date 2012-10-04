"""
"""
import os
import unittest

from beeswithmachineguns import tester 


class AbTesterTestCase(unittest.TestCase):
    """
    """
    
    def test_get_command(self):
        """
        """
        t = tester.ABTester()

        self.assertEqual(
            "ab -r -n 3 -c 6 \"http://magnetic.domdex.com/\"", 
            t.get_command(3, 6, False, 'http://magnetic.domdex.com/')
            )

        self.assertEqual(
            "ab -r -n 10 -c 100 -k \"http://magnetic.domdex.com/\"", 
            t.get_command(10, 100, True, 'http://magnetic.domdex.com/')
            )


    def test_parse_output(self):
        """
        """
        def read_file(name):
            return open(os.path.join(os.path.dirname(__file__), name),'rb').read()
        
        t = tester.ABTester()
        
        self.assertEqual(
            tester.TesterResult(
                concurrency=100.0
              , time_taken=24.544
              , complete_requests=62500.0
              , failed_requests=24688.0
              , non_2xx_responses=37813.0
              , total_transferred=16551810.0
              , requests_per_second=2546.4
              , ms_per_request=39.271
              , fifty_percent=26.0
              , ninety_percent=93.0
              ),
            t.parse_output(read_file('ab-output-1.txt'))
            )
        
        self.assertEqual(
            tester.TesterResult(
                concurrency=93.0
              , time_taken=9.663
              , complete_requests=12500.0
              , failed_requests=0.0
              , non_2xx_responses=0.0
              , total_transferred=2062500.0
              , requests_per_second=1293.53
              , ms_per_request=71.896
              , fifty_percent=69.0
              , ninety_percent=83.0
              ),
            t.parse_output(read_file('ab-output-2.txt'))
            )
        

if __name__=='__main__':
    unittest.main()


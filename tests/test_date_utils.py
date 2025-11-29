import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

import unittest
from datetime import datetime, timezone, timedelta
from sdc.utils import date_utils

class TestDateUtils(unittest.TestCase):

    def test_get_past_datetime_str(self):
        # Test with 180 days
        past_str = date_utils.get_past_datetime_str(180)
        self.assertIsInstance(past_str, str)

        # Check if the format is correct
        parsed_date = datetime.strptime(past_str, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
        
        # Check if the date is roughly 180 days ago
        expected_date = datetime.now(timezone.utc) - timedelta(days=180)
        self.assertAlmostEqual(parsed_date, expected_date, delta=timedelta(seconds=5))

if __name__ == '__main__':
    unittest.main()
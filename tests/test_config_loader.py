import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

import unittest
from sdc.utils import config_loader

class TestConfigLoader(unittest.TestCase):

    def setUp(self):
        self.config = {
            "project_paths": {
                "data_folder": "/data",
                "cache_folder": "/data/cache"
            },
            "logging": {
                "log_level": "INFO"
            },
            "top_level_key": "top_value"
        }

    def test_get_config_value(self):
        # Test getting a nested value
        self.assertEqual(config_loader.get_config_value(self.config, "project_paths.cache_folder"), "/data/cache")
        # Test getting a top-level value
        self.assertEqual(config_loader.get_config_value(self.config, "top_level_key"), "top_value")
        # Test getting a non-existent value with default
        self.assertEqual(config_loader.get_config_value(self.config, "project_paths.non_existent", "default"), "default")
        # Test getting a non-existent value without default
        self.assertIsNone(config_loader.get_config_value(self.config, "non.existent.path"))

if __name__ == '__main__':
    unittest.main()
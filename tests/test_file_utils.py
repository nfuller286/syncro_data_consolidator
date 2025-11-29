import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

import unittest
import os
import tempfile
import shutil
from sdc.utils import file_utils

class TestFileUtils(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        # Create test files
        with open(os.path.join(self.test_dir, "test1.txt"), "w") as f:
            f.write("test")
        with open(os.path.join(self.test_dir, "test2.log"), "w") as f:
            f.write("test")
        self.sub_dir = os.path.join(self.test_dir, "subdir")
        os.makedirs(self.sub_dir)
        with open(os.path.join(self.sub_dir, "test3.txt"), "w") as f:
            f.write("test")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_find_files(self):
        # Test non-recursive find
        txt_files = file_utils.find_files(self.test_dir, "*.txt")
        self.assertEqual(len(txt_files), 1)
        self.assertTrue(txt_files[0].endswith("test1.txt"))

        log_files = file_utils.find_files(self.test_dir, "*.log")
        self.assertEqual(len(log_files), 1)
        self.assertTrue(log_files[0].endswith("test2.log"))

        # Should not find files in subdirectory
        all_txt_files = file_utils.find_files(self.test_dir, "*.txt")
        self.assertFalse(any("test3.txt" in s for s in all_txt_files))

    def test_find_files_recursive(self):
        # Test recursive find
        txt_files = file_utils.find_files_recursive(self.test_dir, "*.txt")
        self.assertEqual(len(txt_files), 2)
        self.assertTrue(any("test1.txt" in s for s in txt_files))
        self.assertTrue(any("test3.txt" in s for s in txt_files))

if __name__ == '__main__':
    unittest.main()
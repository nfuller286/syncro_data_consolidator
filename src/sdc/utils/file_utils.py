# -*- coding: utf-8 -*-
"""General file system utilities."""

import glob
import os
from typing import List


def find_files(root_dir: str, pattern: str) -> List[str]:
    """
    Finds all files matching a pattern in a directory (non-recursive).

    Args:
        root_dir: The directory to search in.
        pattern: The glob pattern to match against filenames (e.g., '*.csv').

    Returns:
        A list of absolute paths to the matching files.
    """
    try:
        matched_files = [
            os.path.join(root_dir, f)
            for f in os.listdir(root_dir)
            if os.path.isfile(os.path.join(root_dir, f)) and glob.fnmatch.fnmatch(f, pattern)
        ]
        return matched_files
    except FileNotFoundError:
        return []


def find_files_recursive(root_dir: str, pattern: str) -> List[str]:
    """
    Recursively finds all files matching a pattern in a directory and its subdirectories.

    Args:
        root_dir: The root directory to start the search from.
        pattern: The glob pattern to match against filenames (e.g., '*.jsonl').

    Returns:
        A list of absolute paths to the matching files.
    """
    matched_files = []
    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            if glob.fnmatch.fnmatch(filename, pattern):
                matched_files.append(os.path.join(dirpath, filename))
    return matched_files
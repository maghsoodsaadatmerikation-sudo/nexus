#!/usr/bin/env python3
"""Compatibility entrypoint: run the real, fail-closed preflight.

This historical nested path must never print PASS without doing the checks.
"""

from pathlib import Path
import runpy

runpy.run_path(str(Path(__file__).resolve().parents[1] / 'verify_test_matrix.py'),
               run_name='__main__')

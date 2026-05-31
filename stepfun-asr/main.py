#!/usr/bin/env python3
"""
Standardized entry point for stepfun-asr skill.
This wrapper allows frameworks to invoke: python main.py [args]
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import stepfun_asr

if __name__ == "__main__":
    stepfun_asr.main()

#!/usr/bin/env python3
"""
Standardized entry point for stepfun-image skill.
This wrapper allows frameworks to invoke: python main.py [args]
"""
import sys
import os

# Add the script directory to path so we can import stepfun_image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import stepfun_image
stepfun_image.main()

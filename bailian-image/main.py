#!/usr/bin/env python3
"""
Standardized entry point for bailian-image skill.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bailian_image
bailian_image.main()

#!/usr/bin/env python3
"""
Standardized entry point for bailian-wan-image skill.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bailian_wan_image
bailian_wan_image.main()

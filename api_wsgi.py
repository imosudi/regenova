#!/usr/bin/env python3
"""
REGENOVA Dedicated API WSGI Entry Point for Apache mod_wsgi.
Deployable at /home/mosud/regenova_api/api_wsgi.py.
"""

import sys
import os

# Add application directory to sys.path
APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from api_server import application

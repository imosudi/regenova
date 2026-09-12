#!/usr/bin/env python3
"""
REGENOVA WSGI Entry Point for Apache mod_wsgi.
Deployable at /home/mosud/regenova/wsgi.py.
"""

import sys
import os

# Add application directory to sys.path
APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from web_server import application

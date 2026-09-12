#!/usr/bin/env python3
"""
REGENOVA Backoffice WSGI Entry Point for Apache mod_wsgi.
Deployable at /home/mosud/backend/backend_wsgi.py.
"""

import os
import sys

# Add application directory to sys.path
APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from backend_server import application

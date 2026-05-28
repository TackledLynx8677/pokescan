# ── PythonAnywhere WSGI configuration ─────────────────────────────────────────
#
# INSTRUCTIONS:
#   1. Upload your project to /home/YOUR_USERNAME/pokescan/
#   2. In PythonAnywhere Dashboard → Web → WSGI configuration file,
#      paste the contents of this file (or point to it).
#   3. Replace YOUR_USERNAME below with your actual PythonAnywhere username.
#   4. Set your environment variables in the "Environment variables" section
#      of the Web tab (ROBOFLOW_API_KEY, ROBOFLOW_MODEL_URL, SECRET_KEY).
#
# ──────────────────────────────────────────────────────────────────────────────

import sys
import os

# Add project root to path
project_home = '/home/YOUR_USERNAME/pokescan'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Set environment (PythonAnywhere serves over HTTPS automatically)
os.environ['FLASK_ENV'] = 'production'

# Import the Flask app factory and create the application
from app import create_app
application = create_app()

"""
Pytest configuration for SAT-SA backend tests.
Configures test secret key and common test fixtures.
"""

import os

# Configure test secret key before any app modules import auth
os.environ.setdefault("SAT_SA_SECRET_KEY", "sat-sa-test-secret-key-for-pytest-execution-only-2026")

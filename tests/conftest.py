import os
import sys

# make the repo-root CLI driver (main.py) importable for its unit tests
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

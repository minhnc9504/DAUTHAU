"""Wrapper: python serve.py -> python main.py serve"""
import subprocess
import sys
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
subprocess.run([sys.executable, "main.py", "serve"], check=True)

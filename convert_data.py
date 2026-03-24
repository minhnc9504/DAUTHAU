"""Wrapper: python convert_data.py -> python main.py ingest"""
import subprocess
import sys
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
subprocess.run([sys.executable, "main.py", "ingest"], check=True)

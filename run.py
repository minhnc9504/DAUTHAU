"""Wrapper: python run.py -> python main.py run"""
import subprocess
import sys
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
subprocess.run([sys.executable, "main.py", "run"], check=True)

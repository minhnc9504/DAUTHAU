"""Wrapper: python train_model.py -> python main.py build-index"""
import subprocess
import sys
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
subprocess.run([sys.executable, "main.py", "build-index"], check=True)

#!/usr/bin/env python3
"""
Standalone entry point for Simanalysis.
This script is intended to be the entry point for the PyInstaller executable.
It launches the Web GUI immediately.
"""
import sys
import multiprocessing

# Necessary for PyInstaller on Windows to handle multiprocessing correctly
if sys.platform.startswith('win'):
    multiprocessing.freeze_support()

from simanalysis.web.run import run_web_gui

def main():
    # You can parse args here if you want to support port configuration in the standalone app
    # For now, defaults are fine.
    run_web_gui()

if __name__ == "__main__":
    main()

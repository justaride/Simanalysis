#!/usr/bin/env python3
"""PyInstaller entry point for the Simanalysis stdio bridge sidecar."""
import multiprocessing
import sys

if sys.platform.startswith("win"):
    multiprocessing.freeze_support()

from simanalysis.bridge import main

if __name__ == "__main__":
    sys.exit(main())

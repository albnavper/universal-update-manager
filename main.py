#!/usr/bin/env python3
"""
Universal Update Manager - Entry Point
"""

import sys
from pathlib import Path

# Add src to path
src_dir = Path(__file__).parent / "src"
sys.path.insert(0, str(src_dir))

from ui import main

if __name__ == "__main__":
    main()

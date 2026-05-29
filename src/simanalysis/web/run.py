import sys
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn


def run_web_gui(host: str = "127.0.0.1", port: int = 8000, open_browser_flag: bool = True):
    """
    Launch the Simanalysis Web GUI.
    """
    print("🚀 Starting Simanalysis Web GUI...")
    print(f"   URL: http://{host}:{port}")

    def open_browser():
        time.sleep(1.5)  # Wait for server to start
        webbrowser.open(f"http://{host}:{port}")

    if open_browser_flag:
        threading.Thread(target=open_browser, daemon=True).start()

    # Start backend
    # We use the string import if not frozen, but if frozen (PyInstaller),
    # uvicorn might have trouble with string imports if not configured right.
    # However, passing the app object directly is safer for frozen apps.

    # Configure logging
    log_dir = Path.home() / ".simanalysis"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "simanalysis.log"

    import logging

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.FileHandler(log_file), logging.StreamHandler(sys.stdout)],
    )

    logger = logging.getLogger(__name__)
    try:
        import simanalysis

        version = getattr(simanalysis, "__version__", "unknown")
    except ImportError:
        version = "unknown"

    logger.info(f"Starting Simanalysis v{version}")

    from simanalysis.web.api import app

    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    run_web_gui()

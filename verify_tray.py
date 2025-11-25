import os
import shutil
from pathlib import Path
from simanalysis.analyzers.tray_analyzer import TrayAnalyzer

def create_dummy_tray_files(directory: Path):
    """Create dummy tray files for testing."""
    directory.mkdir(parents=True, exist_ok=True)
    
    # Household Item
    (directory / "0x00000000_0x0000000000000001.trayitem").write_text("Household Name")
    (directory / "0x00000000_0x0000000000000001.hhi").touch()
    (directory / "0x00000000_0x0000000000000001.sgi").touch()
    
    # Lot Item
    (directory / "0x00000000_0x0000000000000002.trayitem").write_text("Lot Name")
    (directory / "0x00000000_0x0000000000000002.blueprint").touch()
    (directory / "0x00000000_0x0000000000000002.bpi").touch()

def verify_tray_analysis():
    """Verify tray analysis logic."""
    test_dir = Path("test_tray")
    if test_dir.exists():
        shutil.rmtree(test_dir)
        
    try:
        print("Creating dummy tray files...")
        create_dummy_tray_files(test_dir)
        
        print("Running Tray Analyzer...")
        analyzer = TrayAnalyzer()
        result = analyzer.analyze_directory(test_dir)
        
        print(f"Found {len(result.items)} items.")
        
        households = [i for i in result.items if i.type == "Household"]
        lots = [i for i in result.items if "Lot" in i.type]
        
        print(f"Households: {len(households)}")
        print(f"Lots: {len(lots)}")
        
        if len(households) == 1 and len(lots) == 1:
            print("SUCCESS: Verification passed!")
        else:
            print("FAILURE: Incorrect item count.")
            
    finally:
        if test_dir.exists():
            shutil.rmtree(test_dir)

if __name__ == "__main__":
    verify_tray_analysis()

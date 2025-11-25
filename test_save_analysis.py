"""Quick test script for Save Analysis backend."""

from pathlib import Path
from simanalysis.scanners.save_scanner import SaveScanner
from simanalysis.analyzers.save_analyzer import SaveAnalyzer

# Find a save file
saves_dir = Path.home() / "Documents/Electronic Arts/The Sims 4/saves"
save_files = list(saves_dir.glob("*.save"))

if not save_files:
    print("No save files found!")
    exit(1)

save_file = save_files[0]
print(f"Testing with: {save_file.name}")

# Test SaveScanner
print("\n--- Testing SaveScanner ---")
scanner = SaveScanner()
try:
    save_data = scanner.scan_save_file(save_file)
    print(f"✓ Successfully scanned save file")
    print(f"  Total resources: {save_data.total_resources}")
    print(f"  CAS items: {len(save_data.cas_resources)}")
    print(f"  Build/Buy items: {len(save_data.build_buy_resources)}")
    print(f"  Other resources: {len(save_data.other_resources)}")
except Exception as e:
    print(f"✗ Error: {e}")
    exit(1)

# Test SaveAnalyzer (limited test)
print("\n--- Testing SaveAnalyzer ---")
mods_dir = Path.home() / "Documents/Electronic Arts/The Sims 4/Mods"

if not mods_dir.exists():
    print("Mods folder not found, skipping analyzer test")
else:
    analyzer = SaveAnalyzer()
    try:
        print("Running analysis (this may take a while)...")
        
        def progress(stage, current, total):
            print(f"  {stage}: {current}/{total}")
        
        result = analyzer.analyze_save(save_file, mods_dir, progress_callback=progress)
        summary = analyzer.get_summary(result)
        
        print(f"\n✓ Analysis complete!")
        print(f"  Total mods: {summary['total_mods']}")
        print(f"  Used mods: {summary['used_mods']} ({summary['used_size_mb']:.1f} MB)")
        print(f"  Unused mods: {summary['unused_mods']} ({summary['unused_size_mb']:.1f} MB)")
        print(f"  Coverage: {summary['coverage_percentage']}%")
        print(f"  Duration: {summary['scan_duration']:.1f}s")
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

print("\n✓ All tests passed!")

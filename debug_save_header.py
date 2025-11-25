import struct
from pathlib import Path

path = Path('/Users/gabrielboen/Documents/Electronic Arts/The Sims 4/Mods/HeraSims_Roses in box.package')
if not path.exists():
    print("File not found")
    exit(1)

print(f"File size: {path.stat().st_size}")

with open(path, 'rb') as f:
    header = f.read(96)
    if len(header) < 96:
        print("Header too short")
        exit(1)
        
    magic = header[0:4]
    print(f"Magic: {magic}")
    
    major = struct.unpack("<I", header[4:8])[0]
    print(f"Major Version: {major}")
    
    print("-" * 20)
    for i in range(0, 96, 4):
        val = struct.unpack("<I", header[i:i+4])[0]
        print(f"Offset {i}: {val}")

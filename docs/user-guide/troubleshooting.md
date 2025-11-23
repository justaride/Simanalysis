# Troubleshooting

Common issues, solutions, and debugging techniques for Simanalysis.

## Installation Issues

### Issue: `pip install simanalysis` fails

**Symptoms:**
```
ERROR: Could not find a version that satisfies the requirement simanalysis
```

**Causes:**
- Package not yet published to PyPI
- Python version incompatible
- Network issues

**Solutions:**

**1. Install from source:**
```bash
git clone https://github.com/justaride/Simanalysis.git
cd Simanalysis
pip install -e .
```

**2. Check Python version:**
```bash
python --version  # Must be 3.9+
```

**3. Upgrade pip:**
```bash
python -m pip install --upgrade pip
```

**4. Use Docker instead:**
```bash
docker pull simanalysis:latest
```

### Issue: Import errors after installation

**Symptoms:**
```python
>>> import simanalysis
ModuleNotFoundError: No module named 'simanalysis'
```

**Causes:**
- Installed in wrong Python environment
- Virtual environment not activated
- Path issues

**Solutions:**

**1. Check which Python:**
```bash
which python
which pip
# Should point to same environment
```

**2. Use python -m pip:**
```bash
python -m pip install simanalysis
```

**3. Verify installation:**
```bash
python -c "import simanalysis; print(simanalysis.__version__)"
```

**4. Reinstall in correct environment:**
```bash
# Activate virtual environment first
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate  # Windows

# Then install
pip install simanalysis
```

### Issue: Permission denied during installation

**Symptoms:**
```
ERROR: Could not install packages due to an EnvironmentError: [Errno 13] Permission denied
```

**Solutions:**

**1. Use --user flag:**
```bash
pip install --user simanalysis
```

**2. Use virtual environment (recommended):**
```bash
python -m venv venv
source venv/bin/activate
pip install simanalysis
```

**3. Last resort - sudo (not recommended):**
```bash
sudo pip install simanalysis
```

## Runtime Issues

### Issue: Command not found

**Symptoms:**
```bash
$ simanalysis --version
bash: simanalysis: command not found
```

**Causes:**
- Installation path not in PATH
- Virtual environment not activated
- Installed with --user but PATH not configured

**Solutions:**

**1. Use python -m:**
```bash
python -m simanalysis --version
```

**2. Activate virtual environment:**
```bash
source venv/bin/activate
simanalysis --version
```

**3. Add to PATH (--user install):**
```bash
# Linux/macOS
export PATH="$HOME/.local/bin:$PATH"

# Windows
# Add %APPDATA%\Python\Scripts to PATH
```

**4. Create alias:**
```bash
alias simanalysis='python -m simanalysis'
```

### Issue: No mods found

**Symptoms:**
```
🔍 Scanning for mods...
Found 0 mods in /path/to/mods
```

**Causes:**
- Wrong directory path
- No .package or .ts4script files in directory
- Permission issues
- Files in subdirectories and using --no-recursive

**Solutions:**

**1. Verify directory:**
```bash
# Check directory exists
ls -la /path/to/mods

# Count .package files
find /path/to/mods -name "*.package" | wc -l

# Count .ts4script files
find /path/to/mods -name "*.ts4script" | wc -l
```

**2. Use absolute path:**
```bash
# Instead of
simanalysis analyze ./mods

# Use
simanalysis analyze /full/path/to/mods
```

**3. Check permissions:**
```bash
ls -la /path/to/mods
# If not readable, fix permissions:
chmod -R u+r /path/to/mods
```

**4. Use recursive mode:**
```bash
# Ensure --no-recursive is not used
simanalysis analyze ./mods
```

**5. Check file extensions:**
```bash
# Verify files have correct extensions
ls -1 ./mods | grep -E '\.(package|ts4script)$'
```

### Issue: Analysis takes too long

**Symptoms:**
- Analysis runs for 10+ minutes
- Progress bar stuck
- System becomes slow

**Causes:**
- Very large mod collection (1000+ mods)
- Slow disk I/O (HDD)
- Large individual mod files
- Verbose output slowing down

**Solutions:**

**1. Use quiet mode:**
```bash
simanalysis analyze ./mods --quiet --output report.json
```

**2. Limit file types:**
```bash
# Analyze packages only
simanalysis analyze ./mods --extensions .package
```

**3. Use non-recursive for subdirectories:**
```bash
for subdir in ./mods/*/; do
    simanalysis analyze "$subdir" --no-recursive --output "$(basename $subdir).json"
done
```

**4. Check disk performance:**
```bash
# Linux: check I/O wait
iostat -x 1

# If high I/O wait, move mods to faster disk (SSD)
```

**5. Increase resources (Docker):**
```bash
docker run -m 4g --cpus 2 simanalysis:latest analyze /mods
```

### Issue: Out of memory

**Symptoms:**
```
MemoryError: Unable to allocate array
# or
Killed
```

**Causes:**
- Very large mod collection
- Large individual mods (100MB+)
- Insufficient RAM
- Memory leak (bug)

**Solutions:**

**1. Analyze in batches:**
```bash
# Split by subdirectory
for subdir in ./mods/*/; do
    simanalysis analyze "$subdir" --output "$(basename $subdir).json"
done
```

**2. Increase swap space (Linux):**
```bash
# Create 4GB swap file
sudo dd if=/dev/zero of=/swapfile bs=1G count=4
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

**3. Use Docker with memory limit:**
```bash
docker run -m 4g simanalysis:latest analyze /mods
```

**4. Close other applications:**
```bash
# Free up RAM before analysis
```

### Issue: Permission denied reading mods

**Symptoms:**
```
ERROR: Permission denied: /path/to/mods/SomeMod.package
```

**Causes:**
- Files owned by different user
- Restrictive file permissions
- Mods folder protected

**Solutions:**

**1. Fix permissions:**
```bash
# Make files readable
chmod -R u+r /path/to/mods

# Or change ownership
sudo chown -R $USER /path/to/mods
```

**2. Run with sudo (not recommended):**
```bash
sudo simanalysis analyze /path/to/mods
```

**3. Copy mods to accessible location:**
```bash
cp -r /path/to/mods ~/my_mods
simanalysis analyze ~/my_mods
```

### Issue: Corrupted package errors

**Symptoms:**
```
ERROR: Invalid DBPF magic in file: SomeMod.package
ERROR: File too small to contain DBPF header
```

**Causes:**
- File is corrupted
- Incomplete download
- Not a valid .package file
- Zip file renamed to .package

**Solutions:**

**1. Verify file:**
```bash
# Check file size
ls -lh SomeMod.package

# Check if it's a DBPF file
head -c 4 SomeMod.package | od -c
# Should show: D B P F
```

**2. Re-download mod:**
```bash
# Remove corrupted file
rm SomeMod.package

# Download again from mod source
```

**3. Check if it's a zip file:**
```bash
file SomeMod.package
# If says "Zip archive", it might be a script mod:
mv SomeMod.package SomeMod.ts4script
```

**4. Skip corrupted mods:**
```bash
# Move to separate directory
mkdir corrupted
mv SomeMod.package corrupted/

# Analyze remaining mods
simanalysis analyze ./mods
```

## Output Issues

### Issue: No output to console

**Symptoms:**
- Command runs but nothing prints
- Analysis completes silently

**Causes:**
- --quiet flag used
- Output redirected
- Logging level too restrictive

**Solutions:**

**1. Remove --quiet:**
```bash
simanalysis analyze ./mods
```

**2. Check for output redirection:**
```bash
# If running:
simanalysis analyze ./mods > /dev/null
# Remove the redirection
```

**3. Use verbose mode:**
```bash
simanalysis analyze ./mods --verbose
```

**4. Check logs:**
```bash
tail -f ~/.simanalysis/logs/simanalysis.log
```

### Issue: Cannot write output file

**Symptoms:**
```
ERROR: Permission denied: report.json
ERROR: No such file or directory: /invalid/path/report.json
```

**Causes:**
- No write permission in directory
- Parent directory doesn't exist
- Disk full

**Solutions:**

**1. Check directory permissions:**
```bash
ls -ld .
# Should be writable
```

**2. Create parent directory:**
```bash
mkdir -p reports
simanalysis analyze ./mods --output reports/report.json
```

**3. Write to home directory:**
```bash
simanalysis analyze ./mods --output ~/report.json
```

**4. Check disk space:**
```bash
df -h .
```

### Issue: Garbled output or encoding errors

**Symptoms:**
```
UnicodeDecodeError: 'utf-8' codec can't decode byte
```

**Causes:**
- Non-UTF-8 mod file names
- Special characters in paths
- Terminal encoding issues

**Solutions:**

**1. Set UTF-8 encoding:**
```bash
export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8
```

**2. Use JSON output:**
```bash
simanalysis analyze ./mods --output report.json
```

**3. Rename problematic files:**
```bash
# Find files with special characters
find ./mods -name '*[^[:print:]]*'

# Rename or remove
```

## Conflict Detection Issues

### Issue: Expected conflicts not detected

**Symptoms:**
- Know two mods conflict
- Simanalysis reports no conflicts
- Game has issues but analysis shows clean

**Causes:**
- Mods use different instance IDs (not actual conflict)
- Script conflicts not detectable (complex logic)
- Mods in different directories
- Analysis incomplete

**Solutions:**

**1. Check instance IDs:**
```bash
# Extract tuning from both mods using Sims 4 Studio
# Compare instance IDs manually
```

**2. Enable debug logging:**
```bash
simanalysis analyze ./mods --log-level DEBUG --log-file debug.log

# Review log
grep -i "conflict" debug.log
grep -i "instance" debug.log
```

**3. Analyze all mods together:**
```bash
# Ensure all mod directories included
simanalysis analyze ./mods ./cc ./scripts
```

**4. Manual inspection:**
```bash
# List all tuning IDs
jq '.mods[].tunings[].instance_id' report.json | sort | uniq -d
```

### Issue: Too many false positive conflicts

**Symptoms:**
- Hundreds of conflicts reported
- Most are LOW or MEDIUM severity
- Gameplay works fine

**Causes:**
- Large mod collection naturally has overlaps
- Many informational conflicts (not real issues)
- Similar mods with compatible changes

**Solutions:**

**1. Filter by severity:**
```bash
# View only HIGH and CRITICAL
jq '.conflicts[] | select(.severity == "HIGH" or .severity == "CRITICAL")' report.json
```

**2. Focus on critical issues:**
```bash
simanalysis analyze ./mods --output report.json
critical=$(jq '[.conflicts[] | select(.severity == "CRITICAL")] | length' report.json)
echo "Critical conflicts: $critical"
```

**3. Test gameplay:**
```
If gameplay works fine, LOW/MEDIUM conflicts are usually safe to ignore
```

**4. Create baseline:**
```bash
# Save current state as "known good"
simanalysis analyze ./mods --output baseline.json

# After adding mods, compare
simanalysis analyze ./mods --output current.json
diff <(jq -S . baseline.json) <(jq -S . current.json)
```

## Performance Issues

### Issue: High CPU usage

**Symptoms:**
- Fan spinning loudly
- System slow during analysis
- CPU usage 100%

**Causes:**
- Normal during analysis (CPU-intensive)
- Very large mod collection
- Debug logging overhead

**Solutions:**

**1. Run with lower priority:**
```bash
# Linux/macOS
nice -n 19 simanalysis analyze ./mods

# Windows
start /LOW simanalysis analyze ./mods
```

**2. Disable verbose output:**
```bash
simanalysis analyze ./mods --quiet --output report.json
```

**3. Run in background:**
```bash
nohup simanalysis analyze ./mods --quiet --output report.json &
```

**4. Analyze during idle time:**
```bash
# Schedule analysis
echo "simanalysis analyze ./mods --output nightly.json" | at 2am
```

### Issue: High disk usage

**Symptoms:**
- Disk activity constant
- Analysis very slow
- High I/O wait

**Causes:**
- Many small files
- Slow HDD
- Fragmented disk

**Solutions:**

**1. Move to SSD:**
```bash
# Copy mods to SSD
cp -r /hdd/mods /ssd/mods
simanalysis analyze /ssd/mods
```

**2. Close disk-intensive programs:**
```bash
# Check disk usage
iotop
# Close other programs using disk
```

**3. Defragment (Windows):**
```
defrag C: /O
```

## Docker Issues

### Issue: Docker container exits immediately

**Symptoms:**
```bash
$ docker run simanalysis:latest
# Container exits with help text
```

**Causes:**
- No command provided
- Default entrypoint shows help

**Solutions:**

**1. Provide analyze command:**
```bash
docker run -v /path/to/mods:/mods simanalysis:latest analyze /mods
```

**2. Use docker-compose:**
```bash
docker-compose run simanalysis analyze /mods
```

### Issue: Cannot access mounted volume

**Symptoms:**
```
Found 0 mods in /mods
```

**Causes:**
- Volume not mounted correctly
- Wrong path in container
- Permission issues

**Solutions:**

**1. Verify mount:**
```bash
# Check if files visible in container
docker run -v /path/to/mods:/mods simanalysis:latest ls -la /mods
```

**2. Use absolute paths:**
```bash
# Not relative paths
docker run -v "$(pwd)/mods":/mods simanalysis:latest analyze /mods
```

**3. Check permissions:**
```bash
# Run as matching user
docker run --user $(id -u):$(id -g) -v /path/to/mods:/mods simanalysis:latest analyze /mods
```

### Issue: Docker out of memory

**Symptoms:**
```
Container killed due to out of memory
```

**Solutions:**

**1. Increase memory limit:**
```bash
docker run -m 4g simanalysis:latest analyze /mods
```

**2. Configure Docker Desktop:**
```
Settings → Resources → Memory → Increase to 4GB+
```

## Logging and Debugging

### Enable Debug Logging

```bash
simanalysis analyze ./mods --log-level DEBUG --log-file debug.log
```

### View Real-Time Logs

```bash
tail -f ~/.simanalysis/logs/simanalysis.log
```

### Common Log Messages

**"Discovered mod: /path/to/mod.package"**
- Normal: Mod found and identified

**"Failed to parse DBPF header"**
- Error: Mod file is corrupted or not a valid package

**"Skipping hidden file"**
- Normal: Hidden files ignored (files starting with .)

**"Resource at offset extends beyond file size"**
- Error: Corrupted package index

**"Failed to decompress resource"**
- Error: Compression issue, file may be damaged

**"Detected tuning conflict: instance 0x..."**
- Normal: Conflict found (this is what we want)

### Debug Checklist

When reporting bugs, include:

```bash
# 1. Version info
simanalysis --version

# 2. System info
python --version
uname -a  # or ver on Windows

# 3. Command used
# (paste exact command)

# 4. Error output
# (paste full error message)

# 5. Debug log
simanalysis analyze ./mods --log-level DEBUG --log-file debug.log
# Upload debug.log

# 6. Sample mod (if possible)
# Share a problematic mod file (if allowed by mod creator)
```

## Getting Help

### Check Documentation

- [Basic Usage](../getting-started/basic-usage.md)
- [Analyzing Mods](analyzing-mods.md)
- [Understanding Conflicts](understanding-conflicts.md)

### Search Existing Issues

Check [GitHub Issues](https://github.com/justaride/Simanalysis/issues) for similar problems.

### Report New Issue

Create a new issue with:
1. Clear title describing problem
2. Steps to reproduce
3. Expected vs actual behavior
4. Debug log (see checklist above)
5. System info

### Community Support

- [GitHub Discussions](https://github.com/justaride/Simanalysis/discussions)
- Mod community forums
- Discord servers (check README)

## Known Issues

### Issue: ResourceWarning about unclosed files

**Status:** Known, low priority

**Impact:** None (warnings only)

**Workaround:** Ignore warnings or run with `-W ignore`

### Issue: Some script conflicts not detected

**Status:** Limitation of static analysis

**Impact:** Complex script conflicts may not be detected

**Workaround:** Test mods in game, check game logs

### Issue: Memory usage grows with mod count

**Status:** Expected behavior

**Impact:** May need more RAM for 1000+ mods

**Workaround:** Analyze in batches

## Best Practices to Avoid Issues

### 1. Keep Simanalysis Updated

```bash
pip install --upgrade simanalysis
```

### 2. Use Virtual Environments

```bash
python -m venv venv
source venv/bin/activate
pip install simanalysis
```

### 3. Regular Backups

```bash
# Backup mods before changes
tar -czf mods_backup.tar.gz ./mods
```

### 4. Test After Changes

```bash
# Analyze after every mod addition
simanalysis analyze ./mods --output report.json
```

### 5. Monitor Logs

```bash
# Check logs regularly
tail ~/.simanalysis/logs/simanalysis.log
```

### 6. Document Your Setup

```bash
# Keep notes on your mod collection
echo "$(date): Added AwesomeMod v2.1" >> mod_log.txt
```

## Platform-Specific Issues

### Windows

**Issue: Path with spaces**
```bash
# Use quotes
simanalysis analyze "C:\Users\Name\Documents\Electronic Arts\The Sims 4\Mods"
```

**Issue: PowerShell execution policy**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### macOS

**Issue: Permission denied (Catalina+)**
- Grant Terminal full disk access in System Preferences → Security & Privacy

**Issue: Command not found after pip install**
```bash
# Add to PATH in ~/.zshrc or ~/.bash_profile
export PATH="$HOME/Library/Python/3.x/bin:$PATH"
```

### Linux

**Issue: Python version conflicts**
```bash
# Use python3 explicitly
python3 -m pip install simanalysis
python3 -m simanalysis analyze ./mods
```

**Issue: Missing dependencies**
```bash
# Install build tools
sudo apt install python3-dev build-essential
# or
sudo yum install python3-devel gcc
```

## Emergency Troubleshooting

If nothing works:

### 1. Clean Installation

```bash
# Uninstall
pip uninstall simanalysis

# Clear cache
rm -rf ~/.simanalysis
rm -rf ~/.cache/pip

# Reinstall
pip install --no-cache-dir simanalysis
```

### 2. Use Docker

```bash
# Bypass system Python entirely
docker pull simanalysis:latest
docker run -v /path/to/mods:/mods simanalysis:latest analyze /mods
```

### 3. Install from Source

```bash
# Latest development version
git clone https://github.com/justaride/Simanalysis.git
cd Simanalysis
pip install -e .
```

### 4. Use Older Version

```bash
# If latest version has issues
pip install simanalysis==2.0.0
```

---

**Version**: 3.0.0 | **Last Updated**: 2025-11-23

**Still having issues?** [Open an issue on GitHub](https://github.com/justaride/Simanalysis/issues/new)

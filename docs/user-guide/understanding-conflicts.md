# Understanding Conflicts

A comprehensive guide to understanding, interpreting, and resolving mod conflicts in The Sims 4.

## What is a Mod Conflict?

A **mod conflict** occurs when two or more mods attempt to modify the same game element in incompatible ways.

### Types of Game Elements

**Tunings:**
- Game mechanics (traits, buffs, interactions)
- Object properties (chairs, tables, decorations)
- NPC behaviors (townies, services)

**Resources:**
- Textures (clothing, objects, terrain)
- Meshes (3D models)
- Animations
- Audio files

**Scripts:**
- Python code that modifies game logic
- Function injections
- Event listeners
- Custom commands

## Conflict Types

### 1. Tuning Conflicts

**What they are:**
Multiple mods contain XML tuning files with the same instance ID.

**Example:**
```
Mod A: trait_confident.xml (Instance: 0x12345678)
  - Confidence gain: +10
  - Moodlet duration: 4 hours

Mod B: trait_confident_enhanced.xml (Instance: 0x12345678)
  - Confidence gain: +25
  - Moodlet duration: 8 hours

CONFLICT: Both mods want to define trait 0x12345678
RESULT: Only the last-loaded mod's version will be used
```

**How they happen:**
- Mod B enhances Mod A but kept the same ID
- Two mods independently edit the same game tuning
- Mod creator forgot to regenerate instance ID

**Impact:**
- One mod's changes are completely ignored
- Game uses only the last-loaded mod's version
- Features from the overridden mod won't work

**Severity:**
- **CRITICAL**: If mods depend on each other (mod B requires mod A's version)
- **HIGH**: If both mods are essential to your gameplay
- **MEDIUM**: If one mod is clearly "better" than the other
- **LOW**: If mods are similar and either version is acceptable

### 2. Resource Conflicts

**What they are:**
Multiple mods contain resources (textures, meshes) with identical hash values.

**Example:**
```
Mod A: custom_shirt.package
  - Resource: DDS texture (Hash: 0xABCDEF01)
  - Type: YA_F_SHIRT

Mod B: recolor_shirt.package
  - Resource: DDS texture (Hash: 0xABCDEF01)
  - Type: YA_F_SHIRT

CONFLICT: Both mods use hash 0xABCDEF01
RESULT: One texture overwrites the other
```

**How they happen:**
- Hash collision (rare, but possible)
- Recolor mod based on original mod
- Copy-paste error in mod creation

**Impact:**
- Visual issues (wrong texture appears)
- One mod's assets don't show up
- Game might look "glitchy"

**Severity:**
- **HIGH**: If both textures are important and visually different
- **MEDIUM**: If textures are similar (recolors)
- **LOW**: If one texture is clearly better quality

### 3. Script Conflicts

**What they are:**
Multiple Python scripts inject into the same game function.

**Example:**
```python
# Mod A: enhanced_commands.ts4script
@inject_to(sims4.commands, 'execute')
def custom_execute(original, *args, **kwargs):
    log.info("Mod A: Command executed")
    return original(*args, **kwargs)

# Mod B: command_logger.ts4script
@inject_to(sims4.commands, 'execute')
def log_execute(original, *args, **kwargs):
    log.info("Mod B: Logging command")
    return original(*args, **kwargs)

CONFLICT: Both inject into sims4.commands.execute
RESULT: Load order determines which runs first
```

**How they happen:**
- Multiple mods want to enhance the same feature
- Both mods try to fix the same bug
- Mods hook into popular functions (autonomy, interactions)

**Impact:**
- Load order matters critically
- One mod may break the other's functionality
- Unpredictable behavior if mods conflict

**Severity:**
- **CRITICAL**: If mods have incompatible logic
- **HIGH**: If execution order matters
- **MEDIUM**: If both mods can coexist with careful load order
- **LOW**: If injections are independent (just logging, etc.)

### 4. Module Name Conflicts

**What they are:**
Two script mods use the same Python module name.

**Example:**
```
Mod A: awesome_mod.ts4script
  - Contains: utils.py

Mod B: better_mod.ts4script
  - Contains: utils.py

CONFLICT: Python can't distinguish between the two utils.py
RESULT: Import errors, one mod fails to load
```

**Impact:**
- One or both mods fail to load
- Import errors in game logs
- Features don't work

**Severity:**
- **CRITICAL**: Prevents mods from loading
- Always requires resolution

## Severity Levels Explained

### 🔴 CRITICAL

**Definition:** Will cause game crashes, corruption, or complete feature failure.

**Characteristics:**
- Game-breaking conflicts
- Data corruption risk
- Core game file modifications
- Incompatible script injections

**Examples:**
```
- Two mods modifying core game initialization
- Conflicting save file format changes
- Circular dependency in scripts
- Malformed DBPF header (corrupted package)
```

**What to do:**
1. **DO NOT play** until resolved
2. Remove one or both conflicting mods
3. Check for compatibility patches
4. Contact mod authors for help

### 🟠 HIGH

**Definition:** Will likely cause gameplay issues, broken features, or visible bugs.

**Characteristics:**
- Important features won't work
- Gameplay mechanics broken
- Frequent errors in logs
- Visual glitches

**Examples:**
```
- Two mods editing same trait with different effects
- Overlapping script injections in autonomy
- Conflicting relationship tunings
- Same interaction ID with different behaviors
```

**What to do:**
1. Review both mods - which is more important?
2. Check for compatibility patches
3. Test with one mod at a time
4. Choose the mod that fits your playstyle

**Resolution time:** Should resolve within a few days

### 🟡 MEDIUM

**Definition:** May cause minor issues, but usually playable.

**Characteristics:**
- Occasional glitches
- Minor visual issues
- Non-essential features affected
- One mod's changes override another's

**Examples:**
```
- Similar tuning modifications (both boost same skill)
- Texture recolors with same hash
- Minor script logging conflicts
- Duplicate but compatible resource definitions
```

**What to do:**
1. Test gameplay - does it bother you?
2. If no issues, can often ignore
3. Choose preferred version if one is clearly better
4. Keep an eye on game logs for errors

**Resolution time:** Can wait weeks or handle at leisure

### 🟢 LOW

**Definition:** Informational only, unlikely to cause any issues.

**Characteristics:**
- Very minor overlaps
- Similar but compatible modifications
- Informational warnings
- No gameplay impact expected

**Examples:**
```
- Two mods use nearby instance IDs (not same)
- Similar module names but different packages
- Compatible script enhancements
- Duplicate resources with identical content
```

**What to do:**
1. No action required
2. Safe to ignore
3. Monitor if you're cautious

## Conflict Detection

### How Simanalysis Detects Conflicts

**Step 1: Parse all mods**
```
For each mod:
  - Read DBPF package structure
  - Extract tuning XML files
  - Parse instance IDs, modules, classes
  - For scripts: parse Python AST
```

**Step 2: Build index**
```
Create maps:
  - instance_id → [list of mods using it]
  - resource_hash → [list of mods with resource]
  - injection_target → [list of scripts injecting]
```

**Step 3: Find overlaps**
```
For each instance_id:
  if len(mods_using_it) > 1:
    → Tuning conflict detected

For each resource_hash:
  if len(mods_with_hash) > 1:
    → Resource conflict detected

For each injection_target:
  if len(scripts_injecting) > 1:
    → Script conflict detected
```

**Step 4: Classify severity**
```
Based on:
  - Conflict type
  - How different the modifications are
  - Whether mods are compatible
  - Impact on gameplay
```

### False Positives

Sometimes Simanalysis reports conflicts that aren't real issues:

**Case 1: Intentional Overrides**
```
Situation: Mod B is a patch for Mod A
Reality: Both mods are designed to work together
Fix: Ignore conflict if gameplay works fine
```

**Case 2: Identical Content**
```
Situation: Two mods include same resource with same content
Reality: No actual conflict, just redundancy
Fix: Safe to ignore or remove one copy
```

**Case 3: Compatible Injections**
```
Situation: Multiple scripts inject same function
Reality: Injections are compatible and work together
Fix: Ensure correct load order, test gameplay
```

**How to verify:**
```bash
# Check conflict details
jq '.conflicts[] | select(.instance_id == "0x12345678")' report.json

# Test with one mod at a time
mv ModB.package ModB.package.bak
# Start game, test features
# Restore ModB.package, remove ModA.package instead
# Start game, test again
# Compare results
```

## Resolution Strategies

### Strategy 1: Choose One Mod

**When to use:**
- Mods do similar things
- One mod is clearly better/more maintained
- You don't need both

**How:**
```bash
# Backup first
mkdir backup
cp conflicting_mod.package backup/

# Remove less-preferred mod
rm ./mods/LessPreferredMod.package

# Verify conflict resolved
simanalysis analyze ./mods --output fixed.json
jq '.conflicts | length' fixed.json
```

### Strategy 2: Use Compatibility Patch

**When to use:**
- Both mods are essential
- Patch exists (check mod pages)
- Mods are popular (patches likely available)

**How:**
1. Search mod page comments for "compatibility"
2. Check mod author's other uploads
3. Search ModTheSims/Patreon for "[Mod A] + [Mod B] patch"
4. Install patch package alongside both mods

**Example:**
```
Have: WickedWhims + BaseGameDraggable
Conflict: Both modify UI
Solution: Install WW_BGD_Compatibility.package
Result: Both mods work together
```

### Strategy 3: Adjust Load Order

**When to use:**
- Script conflicts
- Mods can coexist with correct order
- Documentation specifies load order

**How:**

The Sims 4 loads mods alphabetically:
```
./mods/
  01_CoreMod.package        (loads first)
  02_DependentMod.package   (loads second)
  99_Patches.package        (loads last)
```

**Rename mods to control order:**
```bash
mv AwesomeMod.package 01_AwesomeMod.package
mv BetterMod.package 02_BetterMod.package
```

### Strategy 4: Merge Mods

**When to use:**
- You know how to use Sims 4 Studio
- Mods are simple tuning changes
- No script conflicts

**How:**
1. Open both mods in Sims 4 Studio
2. Export conflicting tunings
3. Manually merge XML (keep desired changes from both)
4. Import merged tuning into new package
5. Remove original mods

**⚠️ Advanced:** Requires understanding of tuning XML structure.

### Strategy 5: Contact Mod Authors

**When to use:**
- Both mods are actively maintained
- Conflict is recent (new version broke compatibility)
- Many users affected

**How:**
1. Check if issue already reported (mod page comments)
2. Post polite bug report with details:
   - Both mod names and versions
   - Conflict description from Simanalysis
   - Game version
   - Screenshots/logs if relevant
3. Wait for response or patch

### Strategy 6: Live With It

**When to use:**
- Conflict is LOW or MEDIUM severity
- No gameplay issues noticed
- Both mods work fine in practice

**How:**
- Monitor game for issues
- Keep conflict report for reference
- If problems arise, revisit resolution

## Common Conflict Scenarios

### Scenario 1: Trait Conflicts

**Situation:**
```
Mod A: Enhanced Traits (instance 0x11111)
Mod B: Trait Overhaul (instance 0x11111)
Severity: HIGH
```

**Analysis:**
- Both mods modify the same trait
- Only one version will load
- Trait may not work as either mod intended

**Resolution:**
```
Option 1: Keep Enhanced Traits (more lightweight)
Option 2: Keep Trait Overhaul (more features)
Option 3: Find compatibility patch
```

**Test:**
```
1. Remove one mod
2. Start new game or load save
3. Use trait in CAS
4. Test in gameplay
5. Verify expected behavior
```

### Scenario 2: CAS Conflicts

**Situation:**
```
Mod A: Custom Clothes (texture hash 0xAAAA)
Mod B: Recolor Pack (texture hash 0xAAAA)
Severity: MEDIUM
```

**Analysis:**
- Hash collision on clothing texture
- One texture won't appear in CAS
- Visual issue but not game-breaking

**Resolution:**
```
Option 1: Keep preferred texture
Option 2: Rename hash in one mod (advanced)
Option 3: Keep both, accept one texture missing
```

**Test:**
```
1. Enter CAS
2. Browse clothing category
3. Check if both items appear
4. Test in live mode
```

### Scenario 3: Script Injection Conflicts

**Situation:**
```
Mod A: Autonomy Tweaks (injects relationship_tracker)
Mod B: Social Overhaul (injects relationship_tracker)
Severity: HIGH
```

**Analysis:**
- Both inject into relationship system
- Load order determines behavior
- May cause unpredictable social interactions

**Resolution:**
```
1. Check mod documentation for load order
2. Rename to control order (01_ prefix, etc.)
3. Test social interactions extensively
4. If issues, remove less essential mod
```

**Test:**
```
1. Have sims interact
2. Monitor relationship changes
3. Check for error logs
4. Test romantic/friendly interactions
5. Verify autonomy behaves correctly
```

### Scenario 4: Multiple Small Conflicts

**Situation:**
```
50 mods, 25 conflicts, all LOW-MEDIUM severity
```

**Analysis:**
- Large mod collection naturally has overlap
- Most conflicts are minor
- Gameplay likely works fine

**Resolution:**
```
1. Filter to HIGH/CRITICAL only:
   jq '.conflicts[] | select(.severity == "HIGH" or .severity == "CRITICAL")' report.json

2. Resolve critical issues first
3. Playtest to see if others cause problems
4. Address only problematic conflicts
```

## Monitoring Conflicts

### Before Game Sessions

```bash
# Quick check
simanalysis analyze ./mods --quiet --output pregame.json

# Any new conflicts?
diff <(jq '.conflicts' previous.json) <(jq '.conflicts' pregame.json)
```

### After Adding Mods

```bash
# Full analysis
simanalysis analyze ./mods --output current.json

# Compare with baseline
jq '.conflicts | length' baseline.json  # 12
jq '.conflicts | length' current.json   # 15
# 3 new conflicts - investigate
```

### Monthly Maintenance

```bash
# Detailed analysis
simanalysis analyze ./mods \
    --log-level DEBUG \
    --output monthly.json

# Track trends
echo "$(date): $(jq '.conflicts | length' monthly.json) conflicts" >> trends.txt
cat trends.txt
# 2025-10-23: 12 conflicts
# 2025-11-23: 15 conflicts
# → Collection getting more complex
```

## Tools and Resources

### Sims 4 Studio
- Merge tuning files
- Regenerate instance IDs
- View package contents
- Create compatibility patches

### Conflict Detection Mods
- Better Exceptions (detailed error logs)
- MC Command Center (test features)

### Community Resources
- ModTheSims forums
- Reddit r/TheSims
- Mod creators' Discord servers

## Best Practices

### 1. Regular Analysis

Analyze mods regularly, not just when problems occur:

```bash
# Weekly check
simanalysis analyze ./mods --output weekly_$(date +%Y%m%d).json
```

### 2. Keep Reports

Archive analysis reports to track changes:

```bash
mkdir -p reports
simanalysis analyze ./mods --output reports/report_$(date +%Y%m%d).json
```

### 3. Document Resolutions

Keep notes on how you resolved conflicts:

```bash
# conflict_log.txt
2025-11-23: Removed BetterTraits v2.1 (conflicts with EnhancedSims v3.0)
2025-11-20: Renamed 01_MCCommandCenter to load first
2025-11-15: Installed WW+MCCC compatibility patch
```

### 4. Test After Changes

Always test gameplay after resolving conflicts:

```
Checklist:
☐ CAS loads without errors
☐ Save game loads
☐ Interactions work correctly
☐ No error notifications
☐ UI functions properly
☐ Custom content appears
```

### 5. Backup Before Resolving

```bash
# Backup entire Mods folder
tar -czf mods_backup_$(date +%Y%m%d).tar.gz ./mods/

# Or use version control
cd mods
git init
git add .
git commit -m "Baseline before conflict resolution"
```

## Next Steps

- Learn analysis techniques in [Analyzing Mods](analyzing-mods.md)
- Export and share reports in [Exporting Reports](exporting-reports.md)
- Troubleshoot issues in [Troubleshooting](troubleshooting.md)
- See examples in [Advanced Examples](../examples/advanced.md)

---

**Version**: 3.0.0 | **Last Updated**: 2025-11-23

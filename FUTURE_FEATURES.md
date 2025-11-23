# Future Feature Roadmap

**Status:** Planning Phase
**Version Target:** v4.0+
**Last Updated:** November 2025

---

## Overview

This document outlines potential future features for Simanalysis based on community needs and technical feasibility. These features are in the planning stage and not yet scheduled for implementation.

---

## Phase 4: Content Management & Discovery

### Feature 4.1: Mod Update Detection & Management

**User Value:**
- Automatically detect when installed mods have newer versions available
- Get direct download links to updated versions
- Track mod version history
- Receive notifications when critical updates are released (bug fixes, game patch compatibility)

**Technical Requirements:**

1. **Mod Registry Database**
   - Central database mapping mod identifiers to download sources
   - Version tracking system
   - Update frequency monitoring
   - Creator/maintainer information

2. **Version Detection System**
   - Extract version info from mod filenames (e.g., "ModName_v2.3.1.package")
   - Parse version from tuning metadata if available
   - Fuzzy matching for mods without standard version format
   - File hash comparison for identical content detection

3. **Platform-Specific Scrapers/APIs**
   - **ModTheSims:** Web scraping or API integration (if available)
   - **Patreon:** OAuth integration for subscriber content
   - **CurseForge:** API integration
   - **Personal Sites:** Generic web scraper with configurable selectors
   - **GitHub Releases:** GitHub API integration
   - **Tumblr:** Tumblr API integration

4. **Update Check Service**
   - Scheduled background checks (daily/weekly)
   - Rate limiting to respect site TOS
   - Cache update information
   - Batch checking to minimize requests

5. **Authentication & Access Management**
   - Patreon OAuth tokens
   - Site-specific credentials (encrypted local storage)
   - Cookie management for sites requiring login
   - Handle early access vs public release timing

**Implementation Challenges:**

❌ **High Complexity Issues:**
- No central mod repository or standard (unlike npm, PyPI, etc.)
- Hundreds of different creators on different platforms
- Many mods behind paywalls or subscriber-only
- Legal/ethical concerns with scraping and link sharing
- Version numbers not standardized or embedded
- Site TOS may prohibit scraping
- Sites frequently change layout/structure

⚠️ **Medium Complexity Issues:**
- Rate limiting across multiple sites
- Handling authentication for multiple platforms
- Disambiguating mods with similar names
- Detecting renamed mods
- Maintenance burden as sites change

✅ **Solvable Issues:**
- Database schema design
- Caching strategy
- Version comparison logic
- GitHub API integration (easiest starting point)

**Phased Implementation Plan:**

**Phase 4.1.1: Core Infrastructure**
- Design mod registry database schema
- Implement version detection from filenames
- Create version comparison logic
- Build update notification system

**Phase 4.1.2: GitHub Integration** (Easiest First)
- Integrate GitHub Releases API
- Track mods hosted on GitHub
- Automatic version detection from release tags
- Direct download link generation

**Phase 4.1.3: ModTheSims Integration**
- Research ModTheSims structure
- Implement scraper/API client
- Handle download pages
- Track update timestamps

**Phase 4.1.4: Additional Platforms** (As Feasible)
- CurseForge API integration
- Patreon OAuth (for subscriber mods)
- Generic scraper framework for personal sites

**Alternative Approach: Community Database**
- Build crowd-sourced mod registry
- Users contribute mod metadata and sources
- Community verification of update links
- Similar to LOOT (Load Order Optimization Tool) for Skyrim
- Lower maintenance burden, but requires active community

**Estimated Effort:** 6-8 weeks for full implementation
**Maintenance:** High (ongoing as sites change)
**Priority:** Medium (useful but complex)

---

### Feature 4.2: Save File & Tray Content Analysis

**User Value:**
- Identify which CC is actually used in a save file
- See which CC is used on specific Sims or lots
- Generate "required CC list" for sharing Sims/households
- Detect missing CC when loading saves
- Clean up unused CC to improve performance
- Verify CC integrity for save files

**Technical Requirements:**

1. **Save File Parser**
   - Parse binary `.save` files (SimData format)
   - Extract Sim data (CAS parts, outfits)
   - Extract lot data (placed objects, build items)
   - Extract household inventory
   - Handle different save file versions

2. **Tray File Parser**
   - Parse `.trayitem` files (individual Sims)
   - Parse `.blueprint` files (rooms/lots)
   - Parse `.bpi` files (household data)
   - Extract CC references from each type

3. **CC Reference Extraction**
   - Identify CAS part instance IDs
   - Identify object instance IDs
   - Identify build/buy item IDs
   - Map instance IDs to installed mods

4. **CC Matching System**
   - Match found IDs to installed mod files
   - Identify source mod for each CC item
   - Detect missing CC (referenced but not installed)
   - Group by mod creator

5. **Usage Analytics**
   - CC usage frequency (across all saves)
   - Most-used vs never-used CC
   - Sim-specific CC inventory
   - Lot-specific CC inventory
   - Outfit-specific CC breakdown

**Use Cases:**

**Use Case 1: "Which CC Do I Actually Use?"**
```bash
simanalysis save-scan ~/Documents/Electronic Arts/The Sims 4/saves/
# Output:
# ✓ Scanned 12 save files
# ✓ Found 1,247 CC items used in saves
# ✓ You have 3,891 CC items installed
#
# Usage Report:
# - 1,247 CC items used (32% of installed CC)
# - 2,644 CC items never used (68% of installed CC)
#
# Most Used CC:
# 1. SkinBlend_Default.package (used in 45 Sims)
# 2. HairStyle_Long_Wavy.package (used in 23 Sims)
# 3. Eyes_Realistic_Pack.package (used in 38 Sims)
```

**Use Case 2: "Share Sim with Required CC List"**
```bash
simanalysis tray-analyze "MySim.trayitem" --output required_cc.txt
# Output:
# Required CC for "Jane Doe":
#
# Skin: Creator: Pyxis - "Skin Overlay v2"
#   Download: https://pyxis.com/skinoverlay
#
# Hair: Creator: Maxis Match - "Long Wavy Hair"
#   Download: https://maxis-match-cc.tumblr.com/hair-pack-2
#
# Eyes: Creator: RealisticEyes - "Eyes Pack 1"
#   Download: https://realisticeyes.net/pack1
#
# [Total: 15 CC items required]
```

**Use Case 3: "Find Missing CC in Save"**
```bash
simanalysis save-check "Save_001.save"
# Output:
# ⚠️ Missing CC Detected:
#
# 12 Sims have missing CC:
# - "John Smith" missing:
#   - Hair (ID: 0x1234567890ABCDEF)
#   - Shoes (ID: 0xABCDEF1234567890)
#
# 3 Lots have missing objects:
# - "Willow Creek - Starter Home"
#   - Missing object: ID 0x9876543210FEDCBA
```

**Use Case 4: "Clean Up Unused CC"**
```bash
simanalysis cc-cleanup --dry-run
# Output:
# ✓ Analyzed 12 saves and 47 Sims in tray
#
# Safe to Remove (never used):
# 2,644 CC files (3.2 GB)
#
# Would you like to:
# 1. Generate removal list (txt)
# 2. Move to backup folder
# 3. Delete permanently
```

**Implementation Details:**

**Save File Format (.save):**
```
Binary Format: SimData
- Header (version, metadata)
- Household data
  - Sim records
    - CAS Parts (clothing, hair, accessories)
    - Traits, skills, relationships
- Lot data
  - Placed objects (instance IDs)
  - Build mode items
- Inventory items
```

**Tray File Format (.trayitem):**
```
Binary Format: SimData + Blueprint
- Sim data (similar to save)
- Preview images
- Metadata (name, age, traits)
- CC dependencies embedded
```

**Parsing Strategy:**
1. Use `dbpf.py` parser (already implemented for .package files)
2. Extend to handle SimData binary format
3. Create specialized parsers for:
   - `.save` (SaveFileParser)
   - `.trayitem` (TrayItemParser)
   - `.blueprint` (BlueprintParser)

**CC Reference Matching:**
```python
class CCReferenceDetector:
    def __init__(self, installed_mods: List[Mod]):
        self.mod_index = self._build_instance_index(installed_mods)

    def _build_instance_index(self, mods: List[Mod]) -> Dict[int, Mod]:
        """Build index of Instance ID -> Mod"""
        index = {}
        for mod in mods:
            for resource in mod.resources:
                index[resource.instance] = mod
        return index

    def match_cc_reference(self, instance_id: int) -> Optional[Mod]:
        """Match instance ID to installed mod"""
        return self.mod_index.get(instance_id)

    def find_missing_cc(self, save_references: List[int]) -> List[int]:
        """Find referenced IDs that don't exist in installed mods"""
        return [id for id in save_references if id not in self.mod_index]
```

**Technical Challenges:**

✅ **Solvable:**
- Binary format parsing (similar to DBPF, well-documented)
- Instance ID extraction
- Matching IDs to installed mods
- Usage tracking and analytics

⚠️ **Medium Complexity:**
- Multiple save file versions (game updates change format)
- Compressed/encrypted sections
- Large save files (performance)
- Handling corrupted saves

❌ **Limitations:**
- Cannot identify CC creator if not in filename/metadata
- Cannot generate download links without mod update database (Feature 4.1)
- Some CC may not have identifiable instance IDs (merged/recolors)

**Phased Implementation:**

**Phase 4.2.1: Core Save Parsing**
- Implement SaveFileParser for binary `.save` files
- Extract Sim CAS part references
- Extract lot object references
- Unit tests with sample saves

**Phase 4.2.2: Tray File Parsing**
- Implement TrayItemParser for `.trayitem` files
- Implement BlueprintParser for `.blueprint` files
- Extract CC references from tray items
- Generate CC lists for Sims

**Phase 4.2.3: CC Matching System**
- Build instance ID index from installed mods
- Match save references to installed mods
- Detect missing CC
- Report matched vs unmatched CC

**Phase 4.2.4: Usage Analytics**
- Track CC usage across all saves
- Usage frequency reports
- Identify unused CC
- Generate cleanup recommendations

**Phase 4.2.5: Integration with Feature 4.1** (Future)
- Generate download links for required CC
- Export shareable CC lists with links
- Auto-download missing CC (if feasible)

**Estimated Effort:** 3-4 weeks
**Maintenance:** Low (save format changes infrequent)
**Priority:** High (high user value, medium complexity)

---

## Phase 5: Advanced Features (Future Exploration)

### Feature 5.1: Real-Time Mod Monitoring
- File system watcher for mod folder
- Automatic re-analysis on mod changes
- Live conflict notifications
- Integration with mod managers

### Feature 5.2: Mod Collection Profiles
- Save/load different mod setups
- Quick switching between profiles
- Profile conflict checking
- Export/import profiles for sharing

### Feature 5.3: Web Dashboard
- Web-based interface for analysis results
- Cloud sync for mod lists
- Community conflict reports
- Collaborative troubleshooting

### Feature 5.4: Mod Manager Integration
- Plugin for Sims 4 Mod Manager
- Plugin for Vortex
- Direct mod installation from Simanalysis
- One-click conflict resolution

### Feature 5.5: Game Integration (Advanced)
- In-game overlay (if possible)
- Real-time performance monitoring
- Automatic crash log analysis
- Smart mod toggling

---

## Community Feedback

### Feature Requests
- [ ] Mod backup/restore system
- [ ] Automatic load order optimization
- [ ] Conflict auto-resolution (safe patches)
- [ ] Mod compatibility database (crowd-sourced)
- [ ] Integration with Sims 4 Studio
- [ ] Mobile app for mod management

### Vote Priority
Create a community poll to prioritize features:
- Save file analysis (Feature 4.2)
- Mod update detection (Feature 4.1)
- Web dashboard (Feature 5.3)
- Mod manager integration (Feature 5.4)

---

## Technical Research Needed

### Research Topic 1: Save File Format
- Document complete save file structure
- Identify all CC reference types
- Test with multiple save versions
- Handle edge cases (corrupted saves, DLC variations)

**Resources:**
- Sims 4 modding wiki
- s4py documentation
- Community reverse engineering efforts

### Research Topic 2: Mod Distribution Platforms
- Survey all major mod hosting platforms
- Document APIs (if available)
- Review Terms of Service for scraping
- Identify authentication requirements

**Platforms to Research:**
- ModTheSims (most popular)
- CurseForge
- Patreon (many creators)
- LoversLab (adult content)
- Tumblr (many individual creators)
- SimsFileShare
- Personal websites/blogs

### Research Topic 3: Legal & Ethical Considerations
- Mod creator attribution requirements
- Download link redistribution policies
- Paywalled content handling
- Early access vs public release
- DMCA/copyright concerns

---

## Implementation Priority Matrix

| Feature | User Value | Technical Complexity | Maintenance | Priority |
|---------|-----------|---------------------|-------------|----------|
| Save File Analysis (4.2) | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ | **HIGH** |
| GitHub Update Detection (4.1.2) | ⭐⭐⭐⭐ | ⭐⭐ | ⭐ | **HIGH** |
| Mod Update Detection (4.1) | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | **MEDIUM** |
| Mod Collection Profiles (5.2) | ⭐⭐⭐⭐ | ⭐⭐ | ⭐ | **MEDIUM** |
| Real-Time Monitoring (5.1) | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | **LOW** |
| Web Dashboard (5.3) | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | **LOW** |

**Legend:**
- ⭐⭐⭐⭐⭐ = Very High
- ⭐⭐⭐⭐ = High
- ⭐⭐⭐ = Medium
- ⭐⭐ = Low
- ⭐ = Very Low

---

## Recommended Implementation Order

### Short-Term (v4.0 - Next 2-3 months)
1. **Feature 4.2.1-4.2.3:** Save file analysis core features
2. **Feature 4.1.2:** GitHub update detection (pilot program)

### Mid-Term (v4.1 - 4-6 months)
3. **Feature 4.2.4:** Usage analytics and cleanup tools
4. **Feature 5.2:** Mod collection profiles
5. **Feature 4.1.3:** ModTheSims integration (if feasible)

### Long-Term (v5.0+ - 6+ months)
6. **Feature 4.1:** Full mod update detection system
7. **Feature 5.1:** Real-time monitoring
8. **Feature 5.3:** Web dashboard

---

## Decision Points

### Question 1: Should we pursue full mod update detection (4.1)?
**Considerations:**
- Very high user value
- Extremely high complexity
- Heavy maintenance burden
- Legal/ethical concerns
- Might be better as community database

**Recommendation:** Start with GitHub integration (4.1.2) as pilot. Evaluate community response before investing in full system.

### Question 2: Should save file analysis include download links?
**Considerations:**
- Depends on Feature 4.1 implementation
- Can start without links (just identify CC)
- Links can be added later

**Recommendation:** Implement save analysis first (4.2.1-4.2.3), add link generation later if Feature 4.1 succeeds.

### Question 3: What format for CC requirement lists?
**Options:**
- Plain text (simple)
- JSON (machine-readable)
- Markdown (readable + linkable)
- HTML (shareable webpage)

**Recommendation:** Start with Markdown (best balance), add other formats based on user requests.

---

## Next Steps

1. ✅ Document future features in this file
2. ⏭️ Gather community feedback on priorities
3. ⏭️ Research save file format in detail
4. ⏭️ Create proof-of-concept for save parsing
5. ⏭️ Research GitHub API integration
6. ⏭️ Decide on implementation schedule for v4.0

---

## Conclusion

**Save file analysis (Feature 4.2)** is the highest-priority future feature:
- High user value (identify used CC, share Sims, cleanup)
- Medium complexity (challenging but achievable)
- Low maintenance (save format stable)
- No legal/ethical concerns
- Can be implemented independently

**Mod update detection (Feature 4.1)** is desirable but complex:
- Very high user value
- Very high complexity
- High maintenance burden
- Legal/ethical considerations
- Should start with pilot (GitHub integration)

**Recommendation:** Begin Phase 4 with Feature 4.2 (Save File Analysis), pilot test Feature 4.1.2 (GitHub updates) in parallel.

---

*Last Updated: November 23, 2025*
*Status: Planning & Community Feedback Phase*

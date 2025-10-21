# Simanalysis Architecture & Roadmap

This document captures the long-term vision for Simanalysis—an end-to-end diagnostic platform that scans Sims 4 mods before launch, monitors them during gameplay, and generates actionable remediation guidance afterwards.

## 1. Static Analysis Layer (Pre-Launch Detection)

The static layer inspects the Mods directory prior to launching The Sims 4, extracting structural metadata and predicting known failure modes.

### 1.1 Package File Deep Inspection

* **DBPF structure parsing** – Extract the `Type`, `Group`, and `Instance` identifiers, offsets, sizes, and compression flags for every resource within a `.package` file. (Implemented in `src/dbpf_parser.py`.)
* **Resource handlers** – Build specialized validators for the most common resource categories:
  * **XML tuning** – Cross-check instance IDs, referenced tuning keys, enumerations, and tunable collections.
  * **SimData** – Ensure XML/SimData pairs share identical instance IDs.
  * **STBL** – Verify localized string tables maintain key integrity.
  * **Image assets** – Confirm DDS/PNG headers and dimensions.
  * **OBJD** – Inspect object definitions for slot compatibility and instance collisions.
* **Conflict taxonomy** – Classify clashes such as tuning overrides, duplicate resources, script injection collisions, and partial overrides, each with severity and remediation hints. Early duplicate/resource and module collision detection now lives in `src/analyzer.py`.

### 1.2 Script Mod Analysis (`.ts4script`)

* **Bytecode inspection** – Read `.pyo`/`.pyc` metadata (Python version, compilation timestamp) and map registered commands, injections, and game hooks.
* **Decompilation pipeline** – Use tools like `uncompyle6` to reconstruct function bodies, identify conflicting injections, deprecated API calls, or missing dependencies.
* **Framework detection** – Recognize external requirements (XML Injector, MC Command Center, etc.) by scanning for characteristic imports or bundled files.

### 1.3 Load Order & `Resource.cfg` Analysis

* Parse `Resource.cfg` to rebuild actual load order considering priority directives and folder depth limits.
* Flag invalid file names, exceeded folder depth (beyond 5 levels), and inter-mod load-order dependencies.

### 1.4 Dependency & DLC Requirements

* Map tuning references to DLC packs (EP/GP/SP) and surface missing content requirements.
* Detect cross-mod dependencies: shared frameworks, required meshes for recolors, and tuning extensions.

### 1.5 Performance Prediction Model

* Aggregate metrics such as total packages, script count, mesh poly counts, texture resolutions, and script complexity to derive a 0–100 score.
* Highlight specific anti-patterns (oversized textures, missing LODs, problematic weight painting) that degrade runtime performance.

## 2. Runtime Instrumentation Layer

When The Sims 4 launches, a companion monitor correlates OS-level telemetry with in-game logs.

### 2.1 Game Launch Monitoring

* Hook `TS4_x64.exe` to profile module loads, DLL injections, package enumeration, and script compilation phases.
* Track file I/O, memory allocation spikes, and Python initialization errors.

### 2.2 Live Gameplay Telemetry

* Capture interaction execution timing, tuning lookups, script callback durations, and CAS rendering metrics.
* Maintain rolling performance counters (frame time, garbage-collection frequency, memory usage).

### 2.3 Log File Correlation

* Parse `lastException.txt`, MC Command Center logs, and mod-specific logs in real time.
* Classify exception patterns (missing tuning, script conflicts, outdated APIs) and map them to the responsible mods.

### 2.4 Save File Health Checks

* Detect dangling references, duplicate spawners, save-size limits, corrupted memories, and invalid relationships introduced by mods.

## 3. Analysis & Reporting Layer

The analysis layer fuses static and runtime insights into clear guidance for players and creators.

### 3.1 Conflict Correlation Engine

* Represent findings as structured `ModConflict` objects containing severity, type, affected mods, and evidence from both static and runtime sources.
* Maintain a conflict taxonomy that covers static-only, runtime-only, and hybrid issues (e.g., tuning collisions, injection failures, performance hotspots).

### 3.2 Intelligent Remediation System

* Offer prioritized fix strategies for each conflict class (load-order adjustments, merges, injector compatibility checks, etc.).
* Provide file-level directions—resource IDs, package names, and tool workflows (Sims 4 Studio steps) when applicable.

### 3.3 Interactive Dashboard & Reports

* Real-time dashboard summarizing session health (FPS trends, memory usage, active issues).
* Post-session HTML reports with executive summaries, conflict lists, performance breakdowns, and dependency graphs.

### 3.4 AI-Assisted Explanations

* Feed structured findings to an LLM prompt tailored for Sims 4 terminology, requesting beginner-friendly explanations, root cause analysis, remediation steps, and prevention tips.

## 4. Advanced Capabilities

### 4.1 Regression Testing System

* Compare scan results across versions to highlight new conflicts, resolved issues, and performance regressions.

### 4.2 Community Knowledge Base

* Crowdsource known incompatibilities, performance profiles, and DLC requirements to accelerate future scans.

### 4.3 Automated Repair Actions

* Safely execute reversible fixes (rename problematic files, reorder load sequences, remove duplicates) after backing up user content.

### 4.4 Creator Tooling Integration

* Provide Sims 4 Studio plug-ins and CI workflows so creators can validate mods before release.

## 5. Phased Implementation Roadmap

1. **Phase 1 – Core Static Analysis (Months 1–3)**: Implement DBPF parsing, tuning conflict detection, script metadata extraction, dependency mapper, and CLI tooling.
2. **Phase 2 – Runtime Monitoring (Months 4–6)**: Add ETW/Frida collectors, log parsers, and basic telemetry dashboard.
3. **Phase 3 – Intelligence & Reporting (Months 7–9)**: Build correlation engine, remediation guidance, HTML reporting, and LLM explanations.
4. **Phase 4 – Advanced Features (Months 10–12)**: Launch knowledge base, automated repairs, Sims 4 Studio integration, and CI helpers.

## 6. Technical Stack Recommendations

* **Core application** – Python 3.10+ for orchestration, Rust for high-performance binary parsing, SQLite for caching, Redis for streaming telemetry.
* **Runtime monitoring** – Windows ETW hooks or Frida instrumentation; optional custom DLL injection for deep telemetry.
* **Frontend/reporting** – React dashboard with D3.js visualizations, Tailwind CSS styling, optional Electron shell for desktop distribution.
* **AI integration** – Claude (or similar) for narrative explanations, local embedding model plus vector store for similarity search.

This roadmap guides how to evolve the lightweight `ModAnalyzer` skeleton into a comprehensive Sims 4 mod diagnostics suite spanning pre-launch checks, live monitoring, and actionable reporting.

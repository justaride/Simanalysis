# Building Simanalysis as a Standalone Application

This guide explains how to build Simanalysis as a standalone executable that launches the Web GUI automatically.

## Prerequisites

- Python 3.9+
- Node.js & npm
- Virtual environment with dependencies installed

## Build Steps

### 1. Build the Frontend

Navigate to the `web` directory and build the React application:

```bash
cd web
npm install
npm run build
cd ..
```

This creates the `web/dist` directory containing the static assets.

### 2. Install PyInstaller

Ensure PyInstaller is installed in your Python environment:

```bash
pip install pyinstaller
```

### 3. Build the Executable

Run PyInstaller using the provided spec file:

```bash
pyinstaller simanalysis.spec --clean --noconfirm
```

### 4. Run the Application

The built application is located in `dist/Simanalysis/`.

**On macOS/Linux:**
```bash
./dist/Simanalysis/Simanalysis
```

**On Windows:**
```cmd
dist\Simanalysis\Simanalysis.exe
```

When you run the executable, it will:
1. Start the internal web server.
2. Automatically open your default web browser to the application.
3. Run completely offline without needing Python or Node.js installed on the target machine.

## Troubleshooting

- **Missing Files**: If the browser opens but shows a 404 or blank page, ensure `web/dist` was correctly built and included. Check `dist/Simanalysis/_internal/web/dist`.
- **Port Conflicts**: The app defaults to port 8000. If this is in use, the server might fail to start.

## Automated Builds

This repository includes a GitHub Actions workflow (`.github/workflows/build_standalone.yml`) that automatically builds the standalone application for Windows, macOS, and Linux.

**Triggers:**
- Pushing to the `main` branch.
- Publishing a release.
- Manual trigger via the "Actions" tab.

**Artifacts:**
The build artifacts (the `Simanalysis` executable folder) are uploaded to the workflow run summary. You can download them from there.

## Manual Release Process

To create a release manually:

1.  **Build**: Follow the "Build Steps" above.
2.  **Verify**: Run the executable to ensure it works.
3.  **Package**:
    - **Windows**: Zip the `dist/Simanalysis` folder.
    - **macOS**: Zip the `dist/Simanalysis` folder (or create a DMG if you have the tools).
    - **Linux**: Tar/Gzip the `dist/Simanalysis` folder.
4.  **Distribute**: Upload the archive to your desired platform (GitHub Releases, website, etc.).

<!-- DEPLOYMENT.md: PyInstaller bundling and distribution guide -->

# Deployment Guide

This document describes how to build standalone executables for Cribbage Game using PyInstaller.

## Prerequisites

```bash
pip install pyinstaller
```

## Building Standalone Executable

### Windows

```bash
# Build single executable
pyinstaller --onefile --windowed \
  --add-data "assets:assets" \
  --add-data "uptacamp_settings.json:." \
  --name CribbageGame \
  main.py

# Output: dist/CribbageGame.exe
```

### macOS

```bash
# Build application bundle
pyinstaller --onedir --windowed \
  --add-data "assets:assets" \
  --add-data "uptacamp_settings.json:." \
  --name CribbageGame \
  main.py

# Output: dist/CribbageGame.app
```

### Linux

```bash
# Build executable
pyinstaller --onedir \
  --add-data "assets:assets" \
  --add-data "uptacamp_settings.json:." \
  --name CribbageGame \
  main.py

# Output: dist/CribbageGame
```

## Build Options

- `--onefile`: Creates single executable (larger, but simpler to distribute)
- `--onedir`: Creates directory with dependencies (smaller executable, requires directory distribution)
- `--windowed`: Disables console window (Windows/macOS)
- `--add-data`: Includes data files in bundle

## Distribution

After building:

1. **Windows**: Share `dist/CribbageGame.exe`
2. **macOS**: Codesign and notarize `dist/CribbageGame.app` (optional)
3. **Linux**: Create .deb or .rpm package, or share `dist/CribbageGame` directory

## Testing Executable

```bash
# Test built executable before distribution
./dist/CribbageGame  # Linux/macOS
dist\CribbageGame.exe  # Windows
```

## Troubleshooting

- **Missing assets**: Verify `--add-data` paths are correct
- **Missing modules**: Check `build/CribbageGame/Analysis-0.log` for import errors
- **Large file size**: Use `--onedir` and compress directory for distribution

See PyInstaller documentation for advanced options.

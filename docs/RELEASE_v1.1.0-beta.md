# Release v1.1.0-beta

## Release Type

Beta test release for Windows desktop testers.

## Download

- Direct beta zip: https://github.com/josephgiardello-cloud/UptaCamp/raw/master/CribbageGame-Windows-Test.zip

## Beta Warning

This beta build is intended for testing and feedback, not stable production use.

- Bugs and balance changes are expected.
- Online service availability may vary (free-tier infrastructure can idle/sleep).
- Save data and compatibility may change between beta builds.

## What's New In This Beta

- Added packaged Windows beta distribution zip at repo root.
- Added `build_windows.ps1` for repeatable one-command Windows packaging.
- Updated default online client endpoints to production API/WS.
- Improved route/base-url failure messaging in online client flow.
- Updated README to reflect actual current project state and desktop-first play model.

## Included Artifacts

- `CribbageGame-Windows-Test.zip`

## Tester Quick Start (Windows)

1. Download and extract `CribbageGame-Windows-Test.zip`.
2. Run `CribbageGame.exe` from extracted folder.
3. For online tests, choose `Play With Friend` from in-game menu.

## Known Limitations

- Browser-only gameplay is not available.
- SmartScreen warnings may appear because the executable is unsigned.
- Large zip artifact is near GitHub's soft recommendation threshold.

## Feedback Requested

Please report issues with:

- startup/crash behavior
- turn flow and scoring correctness
- online matchmaking/connectivity
- UI readability and controls
- AI difficulty pacing

## GitHub Release Checklist

- [ ] Tag created for `v1.1.0-beta`
- [ ] Release title set to `v1.1.0-beta`
- [ ] `This is a pre-release` enabled
- [ ] Release notes copied from this file
- [ ] Download link verified
- [ ] README beta link and warning verified

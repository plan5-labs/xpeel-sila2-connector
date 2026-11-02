# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-11-03

### Added

- UniteLabs CDK connector for the Xpeel automated plate seal remover, ported from
  [plan5-labs/xpeel-sila2](https://github.com/plan5-labs/xpeel-sila2) with the same SiLA interface
  (`org.riken/instruments/AutomatedPlateSealRemoverController/v1`).
- Simulation mode with a simulated instrument, enabled by default, and the `SimulationController` feature.
- `LockController` feature.

[Unreleased]: https://github.com/plan5-labs/xpeel-sila2-connector/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/plan5-labs/xpeel-sila2-connector/releases/tag/v0.1.0

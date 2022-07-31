# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- Rename `managed_fastapi_app` to `managed_asgi_app` for better clarity
- Use `Type` instead of `type` in type hinting to support Python 3.8

## [0.2.2] - 2022-07-28
### Changed
- Debug logs now contain the qualified name of callbacks

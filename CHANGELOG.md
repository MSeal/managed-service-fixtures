# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2023-10-26
### Changed
- Removed dependency on pydantic. Use dataclasses instead.

## [0.2.0] - 2023-03-02
### Changed
- Unpin `pytest-xdist` and `pytest-asyncio` for better comptaibility with other packages

## [0.1.5] - 2022-08-17
### Changed
- Update pyproject.toml with readme / repository info

### Removed
- `structlog` dependency (all logging using vanilla `logging` now)

## [0.1.4] - 2022-08-03
### Added
- Basic open source repo templates
  - Nox for tests and linting
  - Github action to run tests on PRs
  - Github action for releasing to Pypi on tag
  - Code of Conduct, Contributing, and Releasing docs

## [0.1.3] - 2022-08-02
### Changed
- When an env var is set for a service (e.g. `TEST_REDIS_DETAILS`), but no file exists, emit a warning instead of raising an exception

## [0.1.2] - 2022-08-01
### Added
- tests for connecting to cockroach, redis, and vault
- `run-test-services` script example

### Changed
- Rename `managed_fastapi_app` to `managed_asgi_app` for better clarity
- Use `Type` instead of `type` in type hinting to support Python 3.8



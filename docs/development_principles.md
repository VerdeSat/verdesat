# Development Principles

These guidelines summarise how new code should be written so that it
fits cleanly into the VerdeSat codebase.

## General practices

- **Object oriented design** – each class has a single responsibility and
  collaborates with others via clear interfaces. Prefer composition over
  inheritance and use abstract base classes for extensibility.
- **Dependency injection** – pass `ConfigManager`, `Logger`,
  `StorageAdapter` and other services into classes instead of importing
  them inside methods. This keeps modules testable and stateless.
- **Configuration over constants** – avoid magic numbers or strings.
  Defaults live in configuration files under `resources/` and are
  surfaced through `ConfigManager`.
- **Logging** – use `Logger.get_logger()` and avoid `print()`. Library
  code logs to STDOUT, leaving log level control to the CLI.
- **Cloud-ready storage** – read and write files via `StorageAdapter`.
  The default is local filesystem but modules must accept any
  implementation.
- **Reusable helpers** – check existing services before adding new
  functions.  For example, use `convert_to_cog` from
  `services.raster_utils` rather than creating another converter.
- **CLI integration** – CLI commands should be thin wrappers that call
  service classes. Batch commands operate on all AOIs by default so that
  new modules behave consistently.
- **Type hints and docstrings** – all public functions and classes use
  type annotations and short docstrings.
- **Stateless functions** – avoid global variables; each service method
  should produce deterministic output given its inputs.

Adhering to these principles keeps the project modular and ready for
cloud deployments.

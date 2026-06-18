"""qua-libs-core: utilities shared across the qua-libs modality repositories.

This package is intentionally minimal for now. Genuinely shared helpers
(config builders, plotting/simulation utilities, common macros) are migrated
here over time so the modality repos can depend on a single published package
instead of duplicating code.
"""

try:
    # Written at build time by hatch-vcs (see pyproject.toml).
    from ._version import __version__
except ImportError:  # running from a source checkout that was never built
    try:
        from importlib.metadata import PackageNotFoundError, version

        try:
            __version__ = version("qua-libs-core")
        except PackageNotFoundError:
            __version__ = "0.0.0+unknown"
    except ImportError:
        __version__ = "0.0.0+unknown"

__all__ = ["__version__"]

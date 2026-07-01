"""Context Capsules: runtime version resolved from installed distribution metadata."""

from importlib.metadata import version

__version__: str = version("context-capsule")

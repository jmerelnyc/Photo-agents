"""Optional third-party integrations (observability, billing, etc.).

Modules in this package self-activate on import if their corresponding
configuration is present in the user's credentials file. They never raise
on missing config; absence is silent.
"""

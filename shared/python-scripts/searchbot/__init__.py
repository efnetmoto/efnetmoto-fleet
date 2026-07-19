"""searchbot — IRC web-search package for eggdrop.

Note:
    No module in this package imports from ``eggdrop`` or ``eggdrop.tcl``.
    The only file that touches eggdrop is the ``searchbot.py`` entry point
    (pysource target), which owns binds and partyline/IRC I/O. Keeping the
    package eggdrop-free makes every other module unit-testable without a
    running eggdrop.
"""

"""weather — IRC weather package for eggdrop.

Note:
    All modules in this package MUST be importable without an active eggdrop
    runtime, except for prefs.py which intentionally imports from eggdrop.tcl
    to read/write user preferences in the eggdrop userfile.

    Do not add eggdrop imports to any module other than prefs.py.
"""

#!/usr/bin/env tclsh
# tcltest harness for the joingate suite. Discovers every *.test in this
# directory and runs each in its own child interpreter (singleProcess 0) so
# namespace + ::stubs state cannot leak between files.
package require tcltest 2.5

set tcltest::testsDirectory [file dirname [file normalize [info script]]]
# Run each .test in its own child interpreter so ::stubs / ::joingate state
# cannot leak between files.
set tcltest::singleProcess 0
tcltest::configure -verbose bps

tcltest::runAllTests

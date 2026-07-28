# stubs.tcl — recording stubs for eggdrop commands, so joingate.tcl can be
# `source`d and unit-tested in plain tclsh with no eggdrop runtime.
#
# Each stub records its call into ::stubs::calls (a list of call-tuples) so
# tests can assert on the side-effect sequence. Return values that eggdrop
# would derive from runtime state (isvoice, botisop, chanlist, getchanhost,
# nick2hand, dnslookup) are configurable per-test via ::stubs::configure.
#
# Timers: utimer stashes the command instead of running it; tests fire it
# manually via ::stubs::fire / ::stubs::fire-next so no test waits real time.

# Default env so `source joingate.tcl` succeeds; config.test unsets as needed.
if {![info exists ::env(JOINGATE_CHANNEL)]} {
    set ::env(JOINGATE_CHANNEL) "#motorcycles"
}

namespace eval ::stubs {
    variable calls [list]
    variable timers [dict create] ;# tid -> {secs cmd}
    variable counter 0

    variable botisop 1
    variable isvoice [dict create] ;# "$nick $chan" -> "1"|"0"
    variable chanlist [dict create] ;# chan -> {nick ...}
    variable getchanhost [dict create] ;# "$nick $chan" -> uhost
    variable nick2hand [dict create] ;# "$nick $chan" -> handle
    variable dnslookup [dict create] ;# fqdn -> "status S ip IP" | "pending"
}

# Reset all recorded state between tests.
proc ::stubs::reset {} {
    namespace eval ::stubs {
        set calls [list]
        set timers [dict create]
        set counter 0
        set botisop 1
        set isvoice [dict create]
        set chanlist [dict create]
        set getchanhost [dict create]
        set nick2hand [dict create]
        set dnslookup [dict create]
    }
    set ::botnick "Pompone"
}

proc ::stubs::calls {} {
    variable ::stubs::calls
    return $calls
}

# Configure a stubbed return value. kind: isvoice|chanlist|getchanhost|
# nick2hand|dnslookup|botisop. key/value meaning depends on kind.
proc ::stubs::set-isvoice {nick chan val} {
    variable ::stubs::isvoice
    dict set isvoice "$nick $chan" $val
}

proc ::stubs::set-botisop {val} {
    set ::stubs::botisop $val
}

proc ::stubs::set-chanlist {chan nicks} {
    variable ::stubs::chanlist
    dict set chanlist $chan $nicks
}

proc ::stubs::set-getchanhost {nick chan uhost} {
    variable ::stubs::getchanhost
    dict set getchanhost "$nick $chan" $uhost
}

proc ::stubs::set-nick2hand {nick chan handle} {
    variable ::stubs::nick2hand
    dict set nick2hand "$nick $chan" $handle
}

# fqdn result: "status <1|0> ip <addr>" to answer immediately, or "pending"
# to never answer (let the test fire the timeout guard).
proc ::stubs::set-dnslookup {fqdn result} {
    variable ::stubs::dnslookup
    dict set dnslookup $fqdn $result
}

proc ::stubs::live-timers {} {
    variable ::stubs::timers
    return [dict keys $timers]
}

proc ::stubs::fire {tid} {
    variable ::stubs::timers
    set rec [dict get $timers $tid]
    set timers [::joingate::dict-remove $timers $tid]
    uplevel #0 [dict get $rec cmd]
}

# Fire the most-recently-created live timer. Convenience for single-timer flows.
proc ::stubs::fire-next {} {
    variable ::stubs::timers
    set keys [dict keys $timers]
    if {[llength $keys] == 0} {error "no live timers to fire"}
    ::stubs::fire [lindex $keys end]
}

# --- eggdrop command stubs (global procs joingate.tcl calls) ---
#
# Each call is recorded as a flat string ("cmd arg1 arg2 ..."), not a list,
# so test globs like "putserv PRIVMSG #motorcycles :ted: joingate: *" match
# even when a single argument contains spaces (which Tcl would brace in a
# list's string rep).
proc ::stubs::record {cmd args} {
    variable ::stubs::calls
    if {[llength $args]} {
        lappend calls "$cmd [join $args]"
    } else {
        lappend calls $cmd
    }
}

proc putlog {msg} {::stubs::record putlog $msg}
proc putquick {args} {::stubs::record putquick {*}$args}
proc putserv {args} {::stubs::record putserv {*}$args}
proc putdcc {args} {::stubs::record putdcc {*}$args}
proc pushmode {args} {::stubs::record pushmode {*}$args}
proc putkick {args} {::stubs::record putkick {*}$args}
proc newchanban {args} {::stubs::record newchanban {*}$args}
proc bind {args} {::stubs::record bind {*}$args; return ""}
proc unbind {args} {::stubs::record unbind {*}$args}

proc isvoice {nick chan} {
    variable ::stubs::isvoice
    if {[dict exists $isvoice "$nick $chan"]} {
        return [dict get $isvoice "$nick $chan"]
    }
    return "0"
}

proc botisop {chan} {
    variable ::stubs::botisop
    return $::stubs::botisop
}

proc chanlist {chan} {
    variable ::stubs::chanlist
    if {[dict exists $chanlist $chan]} {return [dict get $chanlist $chan]}
    return [list]
}

proc getchanhost {nick chan} {
    variable ::stubs::getchanhost
    if {[dict exists $getchanhost "$nick $chan"]} {
        return [dict get $getchanhost "$nick $chan"]
    }
    return "user@$nick"
}

proc nick2hand {nick chan} {
    variable ::stubs::nick2hand
    if {[dict exists $nick2hand "$nick $chan"]} {
        return [dict get $nick2hand "$nick $chan"]
    }
    return "*"
}

proc utimer {secs cmd args} {
    variable ::stubs::counter
    variable ::stubs::timers
    set tid "timer[incr ::stubs::counter]"
    dict set timers $tid [dict create secs $secs cmd $cmd]
    return $tid
}

proc killutimer {tid} {
    variable ::stubs::timers
    set timers [::joingate::dict-remove $timers $tid]
}

# dnslookup <fqdn> <proc> [args]: invokes <proc> synchronously with the
# configured result, or not at all if set to "pending".
proc dnslookup {fqdn cb args} {
    variable ::stubs::dnslookup
    if {[dict exists $dnslookup $fqdn]} {
        set res [dict get $dnslookup $fqdn]
        if {[lindex $res 0] eq "pending"} {return}
        set status [lindex $res 1]
        set ip [lindex $res 2]
    } else {
        # Default: immediate NXDOMAIN (clean).
        set status 0
        set ip ""
    }
    uplevel #0 [linsert $args 0 {*}$cb $ip $fqdn $status]
}

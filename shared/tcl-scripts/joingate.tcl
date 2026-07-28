# joingate.tcl — EFNetMoto Anti-Troll Join-Gate
#
# Join-gated voice for a single configured channel. Unknown joiners get no
# voice until either a clean soak elapses or an op manually vets them. Known
# regulars (userfile record) and allowlisted hostmasks skip the gate.
# RBL-positive joiners get a long soak, a single WALLCHOPS notice on
# survival, and a kick-ban if no op acts within a follow-up window.
#
# All soak / allowlist / blocklist state is in-memory and lost on
# rehash/restart, by design (PRD FR-O3, FR-M5). The channel mode +m itself is
# owned by Ansible (FR-O2); this plugin never sets or unsets channel modes.
#
# Companion to the PRD and the TCL implementation plan. Target: Tcl 8.6
# (eggdrop 1.10.1 on Alpine 3.23). No Tcl-9-only APIs (no dict unset/remove/
# getdef/map/filter; no lpop/lremove/string insert).

namespace eval ::joingate {
    variable version "1.0.0"

    # Configuration dict; populated by ::joingate::config::load at load time.
    variable cfg {}

    # In-memory soak state lives in ::joingate::soak (Records / KeyTimers);
    # see that namespace. RBL pending state lives here as RblPending.

    # In-progress RBL lookups: dict key(user@host) -> pending record dict.
    variable RblPending [dict create]

    # Ephemeral trust overrides (in-memory only, cleared on rehash).
    namespace eval trust {
        variable Blocked [list]
        variable Allowed [list]
    }

    # Registered binds: list of 4-tuples {type flags mask proc} for teardown.
    variable Binds [list]

    # All live joingate utimer ids (tid -> 1), so unload can kill every one.
    variable Timers [dict create]

    # Bootstrap-voice retry tuning (the bot is not opped the instant it joins).
    variable BootstrapRetries 12
    variable BootstrapInterval 5
}

# ---------------------------------------------------------------------------
# Small 8.6-safe helpers (the standard dict unset/getdef arrived in 8.7+).
# ---------------------------------------------------------------------------

# Return a copy of dict $d with $key removed. Pure.
proc ::joingate::dict-remove {d key} {
    set new [dict create]
    dict for {k v} $d {
        if {$k ne $key} {dict set new $k $v}
    }
    return $new
}

# Schedule a utimer and track it for bulk cancellation on unload. Returns tid.
proc ::joingate::make-timer {secs cmd} {
    variable Timers
    set tid [utimer $secs $cmd]
    dict set Timers $tid 1
    return $tid
}

# Cancel a tracked utimer (no-op if already fired or unknown).
proc ::joingate::cancel-timer {tid} {
    variable Timers
    if {[dict exists $Timers $tid]} {
        catch {killutimer $tid}
        set Timers [::joingate::dict-remove $Timers $tid]
    }
}

# Kill every live joingate timer (used on unload/rehash).
proc ::joingate::cancel-all-timers {} {
    variable Timers
    dict for {tid _} $Timers {catch {killutimer $tid}}
    set Timers [dict create]
}

# ---------------------------------------------------------------------------
# Configuration (::joingate::config::*)
# ---------------------------------------------------------------------------

namespace eval ::joingate::config {
    # Default WALLCHOPS template. Tokens substituted via string map at notice
    # build time: %hostmask% %nick% %secs% %providers% %cmd%
    variable default_wallchop_template \
        "joingate: %hostmask% (nick %nick%, %secs%s since join, RBL: %providers%) - vet with: %cmd%"
}

# Read/validate ::env once at load. Fails loudly (error) on a missing required
# var so misconfiguration shows in eggdrop's log at source time (FR-C1).
proc ::joingate::config::load {} {
    set cfg [dict create \
        channel [env-required JOINGATE_CHANNEL] \
        rbl_providers [env-list JOINGATE_RBL_PROVIDERS "efnetrbl.org"] \
        soak_clean [env-int JOINGATE_SOAK_CLEAN_SECONDS 30] \
        soak_rbl [env-int JOINGATE_SOAK_RBL_HIT_SECONDS 300] \
        op_window [env-int JOINGATE_OP_RESPONSE_WINDOW_SECONDS 300] \
        rbl_timeout [env-float JOINGATE_RBL_LOOKUP_TIMEOUT_SECONDS 3.0] \
        enabled [env-bool JOINGATE_ENABLED 1] \
        wallchop_tpl [env-str JOINGATE_WALLCHOP_TEMPLATE \
            $::joingate::config::default_wallchop_template]]
    return $cfg
}

proc ::joingate::config::env-required {name} {
    if {![info exists ::env($name)] || $::env($name) eq ""} {
        error "joingate: $name environment variable is not set.\
               Set it in the bot's .env file or Ansible host_vars."
    }
    return $::env($name)
}

# Private: raw env value, or $dflt if unset/empty.
proc ::joingate::config::env-value {name dflt} {
    if {![info exists ::env($name)] || $::env($name) eq ""} {
        return $dflt
    }
    return $::env($name)
}

proc ::joingate::config::env-str {name dflt} {
    return [env-value $name $dflt]
}

proc ::joingate::config::env-int {name dflt} {
    set raw [env-value $name $dflt]
    if {![string is integer -strict $raw]} {
        error "joingate: $name must be an integer, got \"$raw\"."
    }
    return [expr {$raw + 0}]
}

proc ::joingate::config::env-float {name dflt} {
    set raw [env-value $name $dflt]
    if {![string is double -strict $raw]} {
        error "joingate: $name must be a number, got \"$raw\"."
    }
    return [expr {$raw + 0.0}]
}

proc ::joingate::config::env-bool {name dflt} {
    set raw [string tolower [env-value $name $dflt]]
    switch -- $raw {
        1 - yes - true - on {return 1}
        0 - no - false - off {return 0}
        default {
            error "joingate: $name must be boolean (1/0/yes/no/true/false), got \"$raw\"."
        }
    }
}

# Comma-separated -> Tcl list; trims whitespace; drops empties; >=1 required.
proc ::joingate::config::env-list {name dflt} {
    set raw [env-value $name $dflt]
    set items [list]
    foreach part [split $raw ","] {
        set part [string trim $part]
        if {$part ne ""} {lappend items $part}
    }
    if {[llength $items] == 0} {
        error "joingate: $name must list at least one provider."
    }
    return $items
}

# ---------------------------------------------------------------------------
# Hostmask / IP math (::joingate::hostmask::*)
# ---------------------------------------------------------------------------

namespace eval ::joingate::hostmask {}

# Parse "nick!user@host" (or "user@host") -> dict nick user host. Pure.
proc ::joingate::hostmask::parse {hostmask} {
    set at [string last "@" $hostmask]
    if {$at == -1} {
        return [dict create nick "" user "" host $hostmask]
    }
    set host [string range $hostmask [expr {$at + 1}] end]
    set bang [string last "!" $hostmask]
    if {$bang == -1 || $bang > $at} {
        # "user@host" form (a bind uhost).
        set user [string range $hostmask 0 [expr {$at - 1}]]
        return [dict create nick "" user $user host $host]
    }
    set nick [string range $hostmask 0 [expr {$bang - 1}]]
    set user [string range $hostmask [expr {$bang + 1}] [expr {$at - 1}]]
    return [dict create nick $nick user $user host $host]
}

# Host part of a uhost ("user@host" -> "host"). Pure.
proc ::joingate::hostmask::host-of {uhost} {
    set at [string last "@" $uhost]
    if {$at == -1} {return $uhost}
    return [string range $uhost [expr {$at + 1}] end]
}

# Build a ban mask from a uhost: *!*@<host>. Pure.
proc ::joingate::hostmask::ban-mask {uhost} {
    return "*!*@[host-of $uhost]"
}

proc ::joingate::hostmask::is-ipv4 {str} {
    set parts [split $str "."]
    if {[llength $parts] != 4} {return 0}
    foreach p $parts {
        if {![string is integer -strict $p]} {return 0}
        if {$p < 0 || $p > 255} {return 0}
    }
    return 1
}

# Treat anything containing ":" as IPv6-ish (incl. IPv4-mapped ::ffff:1.2.3.4).
proc ::joingate::hostmask::is-ipv6 {str} {
    return [expr {[string first ":" $str] != -1}]
}

proc ::joingate::hostmask::is-ip {str} {
    return [expr {[is-ipv4 $str] || [is-ipv6 $str]}]
}

# 1.2.3.4 -> 4.3.2.1 for RBL queries. Pure.
proc ::joingate::hostmask::reverse-ipv4 {ip} {
    return [join [lreverse [split $ip "."]] "."]
}

# IPv6 nibble reverse for RBL queries (ip6.arpa format). Pure.
proc ::joingate::hostmask::reverse-ipv6 {ip} {
    set ip [string tolower $ip]
    set groups [split $ip ":"]
    # Expand "::" (one run of empty groups) to fill to 8 groups.
    set idx [lsearch $groups ""]
    if {$idx >= 0 && [llength $groups] < 8} {
        set need [expr {8 - [llength $groups] + 1}]
        set fill [lrepeat $need "0"]
        set groups [lreplace $groups $idx $idx {*}$fill]
    }
    set nibbles [list]
    foreach g $groups {
        if {[string match "*.*" $g]} {
            # IPv4-mapped tail: dotted-quad -> 32-bit hex.
            set q [split $g "."]
            set val [expr {
                ([lindex $q 0] << 24) | ([lindex $q 1] << 16)
                | ([lindex $q 2] << 8) | [lindex $q 3]
            }]
            set g [format "%08x" $val]
        }
        set g [format "%04s" $g]
        foreach c [split $g ""] {lappend nibbles $c}
    }
    return [join [lreverse $nibbles] "."]
}

# Dispatch reverse to the right family. Returns "" for a non-IP input. Pure.
proc ::joingate::hostmask::reverse-ip {ip} {
    if {[is-ipv4 $ip]} {return [reverse-ipv4 $ip]}
    if {[is-ipv6 $ip]} {return [reverse-ipv6 $ip]}
    return ""
}

# ---------------------------------------------------------------------------
# RBL (::joingate::rbl::*)
# ---------------------------------------------------------------------------

namespace eval ::joingate::rbl {}

# Pure: aggregate per-provider outcomes -> verdict dict.
#   outcomes: dict provider -> {listed | clean | error}
#   returns:  dict positive 0|1 providers {list}
# Fail closed: any "listed" OR any "error" => positive (FR-R4).
proc ::joingate::rbl::compute {outcomes} {
    set positive 0
    set providers [list]
    dict for {prov outcome} $outcomes {
        if {$outcome eq "listed" || $outcome eq "error"} {
            set positive 1
            lappend providers $prov
        }
    }
    return [dict create positive $positive providers $providers]
}

# Eggdrop-bound (async): fire forward resolution (if needed) then per-provider
# RBL dnslookup's, each guarded by a utimer timeout. Calls $callback with the
# verdict dict when every provider has answered or timed out. Fail-closed
# throughout (FR-R2, FR-R4). Tested with fake dnslookup/utimer stubs.
proc ::joingate::rbl::lookup {uhost callback} {
    variable ::joingate::cfg
    variable ::joingate::RblPending
    set key $uhost
    # Drop any stale pending lookup for this key (defensive; gate guards this).
    if {[dict exists $RblPending $key]} {
        ::joingate::rbl::cancel-pending $key
    }
    set host [::joingate::hostmask::host-of $uhost]
    if {[::joingate::hostmask::is-ip $host]} {
        # IP fast-path: skip forward resolution.
        ::joingate::rbl::start-rbl $key $host $callback
        return
    }
    # Forward-resolve the hostname to an IP (async, fail-closed on miss).
    set rec [dict create callback $callback phase forward ip "" forward_guard ""]
    dict set RblPending $key $rec
    set timeout [dict get $cfg rbl_timeout]
    set tid [::joingate::make-timer $timeout \
        [list ::joingate::rbl::_forward-timeout $key]]
    dict set RblPending $key forward_guard $tid
    dnslookup $host [list ::joingate::rbl::_forward-cb $key]
}

proc ::joingate::rbl::_forward-cb {key ip hostname status} {
    variable ::joingate::RblPending
    if {![dict exists $RblPending $key]} {return}
    set rec [dict get $RblPending $key]
    set guard [dict get $rec forward_guard]
    if {$guard ne ""} {::joingate::cancel-timer $guard}
    if {$status ne "1"} {
        # Unresolvable hostname -> fail closed.
        ::joingate::rbl::finish $key [dict create positive 1 providers {unresolved-host}]
        return
    }
    set callback [dict get $rec callback]
    ::joingate::rbl::start-rbl $key $ip $callback
}

proc ::joingate::rbl::_forward-timeout {key} {
    variable ::joingate::RblPending
    if {![dict exists $RblPending $key]} {return}
    ::joingate::rbl::finish $key [dict create positive 1 providers {unresolved-host}]
}

# Fire per-provider RBL lookups for a resolved IP. Each gets a timeout guard.
proc ::joingate::rbl::start-rbl {key ip callback} {
    variable ::joingate::cfg
    variable ::joingate::RblPending
    set providers [dict get $cfg rbl_providers]
    set n [llength $providers]
    set qname [::joingate::hostmask::reverse-ip $ip]
    set rec [dict create callback $callback phase rbl total $n answered 0 \
        outcomes [dict create] ip $ip guards [dict create]]
    dict set RblPending $key $rec
    set timeout [dict get $cfg rbl_timeout]
    foreach prov $providers {
        set fqdn "$qname.$prov"
        set guard [::joingate::make-timer $timeout \
            [list ::joingate::rbl::_timeout $key $prov]]
        dict set RblPending $key guards $prov $guard
        dnslookup $fqdn [list ::joingate::rbl::_dns-cb $key $prov]
    }
}

# Per-provider dnslookup callback: ip hostname status.
proc ::joingate::rbl::_dns-cb {key prov ip hostname status} {
    variable ::joingate::RblPending
    if {![dict exists $RblPending $key]} {return}
    set rec [dict get $RblPending $key]
    # Ignore duplicates / late answers that arrived after the timeout guard.
    if {[dict exists [dict get $rec outcomes] $prov]} {return}
    set guards [dict get $rec guards]
    if {[dict exists $guards $prov]} {
        ::joingate::cancel-timer [dict get $guards $prov]
    }
    if {$status eq "1"} {
        if {[string match "127.0.0.*" $ip]} {
            set outcome listed
        } else {
            # Resolved but not a 127.0.0.x RBL answer: weird, fail closed.
            set outcome error
        }
    } else {
        # Fast NXDOMAIN -> clean (slow/missing is handled by _timeout -> error).
        set outcome clean
    }
    dict set RblPending $key outcomes $prov $outcome
    dict set RblPending $key answered [expr {[dict get $rec answered] + 1}]
    ::joingate::rbl::maybe-finish $key
}

# Per-provider timeout guard fired: no answer in time -> error (fail closed).
proc ::joingate::rbl::_timeout {key prov} {
    variable ::joingate::RblPending
    if {![dict exists $RblPending $key]} {return}
    set rec [dict get $RblPending $key]
    if {[dict exists [dict get $rec outcomes] $prov]} {return}
    dict set RblPending $key outcomes $prov error
    dict set RblPending $key answered [expr {[dict get $rec answered] + 1}]
    ::joingate::rbl::maybe-finish $key
}

proc ::joingate::rbl::maybe-finish {key} {
    variable ::joingate::RblPending
    set rec [dict get $RblPending $key]
    if {[dict get $rec answered] < [dict get $rec total]} {return}
    set verdict [::joingate::rbl::compute [dict get $rec outcomes]]
    ::joingate::rbl::finish $key $verdict
}

# Compute done (or fail-closed short-circuit): deliver verdict, drop pending.
proc ::joingate::rbl::finish {key verdict} {
    variable ::joingate::RblPending
    if {![dict exists $RblPending $key]} {return}
    set rec [dict get $RblPending $key]
    ::joingate::rbl::cancel-pending $key
    set callback [dict get $rec callback]
    {*}$callback $verdict
}

# Cancel a pending lookup: kill any live guards, drop the record.
proc ::joingate::rbl::cancel-pending {key} {
    variable ::joingate::RblPending
    if {![dict exists $RblPending $key]} {return}
    set rec [dict get $RblPending $key]
    if {[dict exists $rec forward_guard]} {
        ::joingate::cancel-timer [dict get $rec forward_guard]
    }
    if {[dict exists $rec guards]} {
        dict for {prov tid} [dict get $rec guards] {
            ::joingate::cancel-timer $tid
        }
    }
    set RblPending [::joingate::dict-remove $RblPending $key]
}

# ---------------------------------------------------------------------------
# Soak state (::joingate::soak::*)
# ---------------------------------------------------------------------------

namespace eval ::joingate::soak {
    variable Records [dict create]
    variable KeyTimers [dict create]
}

proc ::joingate::soak::start {key rec secs cmd} {
    variable Records
    variable KeyTimers
    set tid [::joingate::make-timer $secs $cmd]
    dict set Records $key $rec
    dict set KeyTimers $key $tid
    return $tid
}

proc ::joingate::soak::reschedule {key newstate secs cmd} {
    variable Records
    variable KeyTimers
    if {[dict exists $KeyTimers $key]} {
        ::joingate::cancel-timer [dict get $KeyTimers $key]
    }
    dict set Records $key state $newstate
    set tid [::joingate::make-timer $secs $cmd]
    dict set KeyTimers $key $tid
    return $tid
}

proc ::joingate::soak::cancel {key} {
    variable Records
    variable KeyTimers
    if {[dict exists $KeyTimers $key]} {
        ::joingate::cancel-timer [dict get $KeyTimers $key]
        set KeyTimers [::joingate::dict-remove $KeyTimers $key]
    }
    set Records [::joingate::dict-remove $Records $key]
}

proc ::joingate::soak::rename {key newnick} {
    variable Records
    if {[dict exists $Records $key]} {
        dict set Records $key nick $newnick
    }
}

proc ::joingate::soak::clear {key} {cancel $key}

proc ::joingate::soak::get {key} {
    variable Records
    if {[dict exists $Records $key]} {return [dict get $Records $key]}
    return ""
}

proc ::joingate::soak::exists {key} {
    variable Records
    return [dict exists $Records $key]
}

# ---------------------------------------------------------------------------
# Trust tiers (::joingate::trust::*)
# ---------------------------------------------------------------------------

proc ::joingate::trust::is-blocked {hostmask} {
    variable Blocked
    foreach glob $Blocked {
        if {[string match -nocase $glob $hostmask]} {return 1}
    }
    return 0
}

proc ::joingate::trust::is-allowed {hostmask} {
    variable Allowed
    foreach glob $Allowed {
        if {[string match -nocase $glob $hostmask]} {return 1}
    }
    return 0
}

proc ::joingate::trust::block {glob} {
    variable Blocked
    if {$glob ni $Blocked} {lappend Blocked $glob}
}

proc ::joingate::trust::allow {glob} {
    variable Allowed
    if {$glob ni $Allowed} {lappend Allowed $glob}
}

# ---------------------------------------------------------------------------
# Manual command parsing (::joingate::cmd::*)
# ---------------------------------------------------------------------------

namespace eval ::joingate::cmd {}

# Parse "command args..." -> dict op target, or "" if unparseable. Pure.
proc ::joingate::cmd::parse {text} {
    set parts [split [string trim $text]]
    if {[llength $parts] < 1} {return ""}
    set cmd [string tolower [lindex $parts 0]]
    switch -- $cmd {
        gatesync {
            return [dict create op sync target ""]
        }
        gatevoice {
            if {[llength $parts] < 2} {return ""}
            return [dict create op voice target [lindex $parts 1]]
        }
        gateblock {
            if {[llength $parts] < 2} {return ""}
            return [dict create op block target [lindex $parts 1]]
        }
        gateallow {
            if {[llength $parts] < 2} {return ""}
            return [dict create op allow target [lindex $parts 1]]
        }
        default {
            return ""
        }
    }
}

# ---------------------------------------------------------------------------
# IRC side-effect wrappers (::joingate::irc::*)
# ---------------------------------------------------------------------------

namespace eval ::joingate::irc {}

proc ::joingate::irc::voice {channel nick} {
    if {![botisop $channel]} {
        putlog "joingate: not opped on $channel; cannot voice $nick"
        return 0
    }
    pushmode $channel +v $nick
    return 1
}

# Ban before kick (FR-T3) so a kick cannot restart the soak for free.
proc ::joingate::irc::kickban {channel nick uhost reason} {
    if {![botisop $channel]} {
        putlog "joingate: not opped on $channel; cannot kick-ban $nick"
        return 0
    }
    set ban [::joingate::hostmask::ban-mask $uhost]
    newchanban $channel $ban $::botnick $reason
    putkick $channel $nick $reason
    return 1
}

proc ::joingate::irc::is-voiced {channel nick} {
    return [expr {[isvoice $nick $channel] eq "1"}]
}

proc ::joingate::irc::wallchops {channel message} {
    putquick "NOTICE @$channel :$message"
}

proc ::joingate::irc::log {msg} {
    putlog "joingate: $msg"
}

# Reply on any of the three command surfaces. ctx: dict surface target prefix.
proc ::joingate::irc::reply {ctx text} {
    set surface [dict get $ctx surface]
    set target [dict get $ctx target]
    set prefix [dict get $ctx prefix]
    switch -- $surface {
        pub {putserv "PRIVMSG $target :$prefix$text"}
        dcc {putdcc $target "$prefix$text"}
        msg {putserv "PRIVMSG $target :$text"}
    }
}

# ---------------------------------------------------------------------------
# Gate orchestrator (::joingate::gate::*)
# ---------------------------------------------------------------------------

namespace eval ::joingate::gate {}

# bind join -|- *: nick uhost handle channel. Catches all joiners.
proc ::joingate::gate::on_join {nick uhost handle channel} {
    variable ::joingate::cfg
    if {![dict get $cfg enabled]} {return}
    if {$channel ne [dict get $cfg channel]} {return}
    # The bot's own join triggers bootstrap-voice, never the gate.
    if {$nick eq $::botnick} {
        ::joingate::gate::bootstrap-deferred $channel 0
        return
    }
    set hostmask "$nick!$uhost"

    # 1. blocklist -> immediate kick-ban (FR-G4).
    if {[::joingate::trust::is-blocked $hostmask]} {
        ::joingate::irc::kickban $channel $nick $uhost "join-gate: blocklisted"
        ::joingate::irc::log "blocklisted join $hostmask"
        return
    }

    # 2. known user (userfile record) -> immediate voice, no soak (FR-G2).
    if {$handle ne "*"} {
        ::joingate::irc::voice $channel $nick
        ::joingate::irc::log "known join $hostmask (handle $handle)"
        return
    }

    # 3. allowlist -> immediate voice, no RBL (FR-G5).
    if {[::joingate::trust::is-allowed $hostmask]} {
        ::joingate::irc::voice $channel $nick
        ::joingate::irc::log "allowlisted join $hostmask"
        return
    }

    # 4. unknown -> RBL (async) -> soak starts in the callback (FR-G6).
    ::joingate::irc::log "unknown join $hostmask; starting RBL"
    ::joingate::rbl::lookup $uhost \
        [list ::joingate::gate::on_rbl $channel $nick $uhost $hostmask]
}

# RBL verdict in: start the soak (clean -> short, positive -> long).
proc ::joingate::gate::on_rbl {channel nick uhost hostmask verdict} {
    variable ::joingate::cfg
    set key $uhost
    if {[::joingate::soak::exists $key]} {
        # part/sign raced the lookup; drop the verdict.
        return
    }
    set positive [dict get $verdict positive]
    set secs [expr {$positive ? [dict get $cfg soak_rbl] : [dict get $cfg soak_clean]}]
    set state [expr {$positive ? "soaking_rbl" : "soaking_clean"}]
    set rec [dict create \
        channel $channel nick $nick uhost $uhost hostmask $hostmask \
        state $state joined_ms [clock milliseconds] rbl $verdict]
    ::joingate::soak::start $key $rec $secs \
        [list ::joingate::gate::on_soak_expire $channel $key]
    ::joingate::irc::log "soak start $hostmask state=$state secs=$secs\
        rbl_providers=[dict get $verdict providers]"
}

# utimer fires: drive the soak-expiry state machine.
proc ::joingate::gate::on_soak_expire {channel key} {
    variable ::joingate::cfg
    set rec [::joingate::soak::get $key]
    if {$rec eq ""} {return}
    set nick [dict get $rec nick]
    set uhost [dict get $rec uhost]
    set hostmask [dict get $rec hostmask]
    set state [dict get $rec state]

    # FR-T4: already voiced by another op/bot -> clear, no action.
    if {[::joingate::irc::is-voiced $channel $nick]} {
        ::joingate::soak::clear $key
        ::joingate::irc::log "soak cleared (already voiced) $hostmask"
        return
    }

    switch -- $state {
        soaking_clean {
            ::joingate::irc::voice $channel $nick
            ::joingate::soak::clear $key
            ::joingate::irc::log "auto-voice $hostmask (clean soak complete)"
        }
        soaking_rbl {
            ::joingate::irc::wallchops $channel [::joingate::gate::notice $rec]
            set secs [dict get $cfg op_window]
            ::joingate::soak::reschedule $key "awaiting_op" $secs \
                [list ::joingate::gate::on_soak_expire $channel $key]
            ::joingate::irc::log "wallchops sent $hostmask; awaiting op (window ${secs}s)"
        }
        awaiting_op {
            # No op action within the window -> kick-ban (FR-T3). Ban before kick.
            ::joingate::irc::kickban $channel $nick $uhost \
                "join-gate: unvetted RBL-positive"
            ::joingate::soak::clear $key
            ::joingate::irc::log "kick-ban $hostmask (op window expired)"
        }
    }
}

# WALLCHOPS message (FR-N2). Built from the record + the configured template.
proc ::joingate::gate::notice {rec} {
    variable ::joingate::cfg
    set secs [expr {([clock milliseconds] - [dict get $rec joined_ms]) / 1000}]
    set providers [join [dict get [dict get $rec rbl] providers] ", "]
    if {$providers eq ""} {set providers "none"}
    set tpl [dict get $cfg wallchop_tpl]
    return [string map [list \
        "%hostmask%" [dict get $rec hostmask] \
        "%nick%" [dict get $rec nick] \
        "%secs%" $secs \
        "%providers%" $providers \
        "%cmd%" "gatevoice [dict get $rec nick]"] $tpl]
}

# --- cancellation / nick binds (FR-S3, FR-S4, FR-S5) ---

proc ::joingate::gate::on_part {nick uhost handle channel {msg ""}} {
    ::joingate::gate::cancel-soak $uhost "part" $nick
}

proc ::joingate::gate::on_sign {nick uhost handle channel {reason ""}} {
    ::joingate::gate::cancel-soak $uhost "sign" $nick
}

proc ::joingate::gate::on_splt {nick uhost handle channel} {
    ::joingate::gate::cancel-soak $uhost "splt" $nick
}

proc ::joingate::gate::on_nick {nick uhost handle channel newnick} {
    # Keep the soak, update the nick (FR-S4). Key is stable user@host.
    ::joingate::soak::rename $uhost $newnick
    ::joingate::irc::log "nick change during soak: $nick -> $newnick (key $uhost)"
}

proc ::joingate::gate::on_rejn {nick uhost handle channel} {
    # Netsplit return is a fresh gate (FR-S5).
    ::joingate::gate::on_join $nick $uhost $handle $channel
}

proc ::joingate::gate::cancel-soak {uhost reason nick} {
    # Cancel both an active soak and an in-flight RBL lookup (keyed by uhost),
    # so a part/sign/splt during the async RBL window cannot later start a
    # soak (or fire a terminal action) for a user who has already left.
    set cancelled 0
    if {[::joingate::soak::exists $uhost]} {
        ::joingate::soak::cancel $uhost
        set cancelled 1
    }
    if {[dict exists $::joingate::RblPending $uhost]} {
        ::joingate::rbl::cancel-pending $uhost
        set cancelled 1
    }
    if {$cancelled} {
        ::joingate::irc::log "soak cancelled ($reason) for $nick (key $uhost)"
    }
}

# --- manual op commands (FR-M1..M5) ---

# Reply context builders for the three bind surfaces.
proc ::joingate::gate::ctx-pub {channel nick} {
    return [dict create surface pub target $channel prefix "$nick: "]
}

proc ::joingate::gate::ctx-dcc {idx} {
    return [dict create surface dcc target $idx prefix ""]
}

proc ::joingate::gate::ctx-msg {nick} {
    return [dict create surface msg target $nick prefix ""]
}

# Reconstruct "command args" and dispatch via the pure parser.
proc ::joingate::gate::run {cmdword argtext ctx} {
    set parsed [::joingate::cmd::parse "$cmdword $argtext"]
    ::joingate::gate::dispatch $parsed $ctx
}

proc ::joingate::gate::dispatch {parsed ctx} {
    if {$parsed eq ""} {
        ::joingate::irc::reply $ctx \
            "joingate: usage: gatevoice <nick> | gateblock <glob> | gateallow <glob> | gatesync"
        return
    }
    variable ::joingate::cfg
    set channel [dict get $cfg channel]
    set op [dict get $parsed op]
    switch -- $op {
        sync {
            set n [::joingate::gate::bootstrap-voice $channel]
            ::joingate::irc::reply $ctx \
                "joingate: voiced $n known/allowlisted occupant(s) on $channel"
        }
        voice {
            set target [dict get $parsed target]
            ::joingate::gate::manual-voice $channel $target
            ::joingate::irc::reply $ctx "joingate: voiced $target"
        }
        block {
            set glob [dict get $parsed target]
            ::joingate::trust::block $glob
            ::joingate::irc::log "blocklist added: $glob"
            ::joingate::irc::reply $ctx "joingate: blocklisted $glob"
        }
        allow {
            set glob [dict get $parsed target]
            ::joingate::trust::allow $glob
            ::joingate::irc::log "allowlist added: $glob"
            ::joingate::irc::reply $ctx "joingate: allowlisted $glob"
        }
    }
}

# Voice a nick now and cancel any active soak keyed by that nick (FR-M2).
proc ::joingate::gate::manual-voice {channel target} {
    ::joingate::irc::voice $channel $target
    dict for {key rec} $::joingate::soak::Records {
        if {[dict get $rec nick] eq $target} {
            ::joingate::soak::cancel $key
            ::joingate::irc::log "manual voice $target cancelled soak (key $key)"
            break
        }
    }
}

# Voice every current occupant with a userfile handle or allowlist match.
# Returns the count of voices issued. No-op (returns 0) if not opped.
# Used by gatesync and by bootstrap-deferred (after the bot is opped).
proc ::joingate::gate::bootstrap-voice {channel} {
    if {![botisop $channel]} {return 0}
    set count 0
    foreach nick [chanlist $channel] {
        if {$nick eq $::botnick} {continue}
        if {[::joingate::irc::is-voiced $channel $nick]} {continue}
        set uhost [getchanhost $nick $channel]
        set hostmask "$nick!$uhost"
        set handle [nick2hand $nick $channel]
        set known [expr {$handle ne "*" && $handle ne ""}]
        if {$known || [::joingate::trust::is-allowed $hostmask]} {
            ::joingate::irc::voice $channel $nick
            incr count
            ::joingate::irc::log "bootstrap-voice $hostmask (handle $handle)"
        }
    }
    return $count
}

# On the bot's own join: wait until opped, then bootstrap-voice. Handles the
# race where the bot joins (and +m is applied by chanmode) before it has ops.
proc ::joingate::gate::bootstrap-deferred {channel retries} {
    variable ::joingate::BootstrapRetries
    variable ::joingate::BootstrapInterval
    if {![botisop $channel]} {
        if {$retries < $BootstrapRetries} {
            ::joingate::make-timer $BootstrapInterval \
                [list ::joingate::gate::bootstrap-deferred $channel \
                    [expr {$retries + 1}]]
        } else {
            ::joingate::irc::log "bootstrap gave up after $BootstrapRetries tries\
                (never opped on $channel); run 'gatesync' once opped"
        }
        return
    }
    set n [::joingate::gate::bootstrap-voice $channel]
    ::joingate::irc::log "bootstrap-voice voiced $n occupant(s) on $channel"
}

# --- per-surface bind handlers (pub/dcc/msg). Thin adapters to run. ---

proc ::joingate::gate::pub_gatevoice {nick uhost handle channel text} {
    ::joingate::gate::run gatevoice $text [::joingate::gate::ctx-pub $channel $nick]
}
proc ::joingate::gate::pub_gateblock {nick uhost handle channel text} {
    ::joingate::gate::run gateblock $text [::joingate::gate::ctx-pub $channel $nick]
}
proc ::joingate::gate::pub_gateallow {nick uhost handle channel text} {
    ::joingate::gate::run gateallow $text [::joingate::gate::ctx-pub $channel $nick]
}
proc ::joingate::gate::pub_gatesync {nick uhost handle channel text} {
    ::joingate::gate::run gatesync $text [::joingate::gate::ctx-pub $channel $nick]
}

proc ::joingate::gate::dcc_gatevoice {handle idx text} {
    ::joingate::gate::run gatevoice $text [::joingate::gate::ctx-dcc $idx]
}
proc ::joingate::gate::dcc_gateblock {handle idx text} {
    ::joingate::gate::run gateblock $text [::joingate::gate::ctx-dcc $idx]
}
proc ::joingate::gate::dcc_gateallow {handle idx text} {
    ::joingate::gate::run gateallow $text [::joingate::gate::ctx-dcc $idx]
}
proc ::joingate::gate::dcc_gatesync {handle idx text} {
    ::joingate::gate::run gatesync $text [::joingate::gate::ctx-dcc $idx]
}

proc ::joingate::gate::msg_gatevoice {nick uhost handle text} {
    ::joingate::gate::run gatevoice $text [::joingate::gate::ctx-msg $nick]
}
proc ::joingate::gate::msg_gateblock {nick uhost handle text} {
    ::joingate::gate::run gateblock $text [::joingate::gate::ctx-msg $nick]
}
proc ::joingate::gate::msg_gateallow {nick uhost handle text} {
    ::joingate::gate::run gateallow $text [::joingate::gate::ctx-msg $nick]
}
proc ::joingate::gate::msg_gatesync {nick uhost handle text} {
    ::joingate::gate::run gatesync $text [::joingate::gate::ctx-msg $nick]
}

# ---------------------------------------------------------------------------
# Load / unload (rehash-safe)
# ---------------------------------------------------------------------------

proc ::joingate::load {} {
    # Tear down any prior incarnation first (rehash re-sources this file).
    ::joingate::unload
    variable cfg [::joingate::config::load]
    variable Binds [list]

    # Event binds: catch every joiner (-|- = no flag requirement; "*" = all).
    lappend Binds [list join -|- * ::joingate::gate::on_join]
    lappend Binds [list part -|- * ::joingate::gate::on_part]
    lappend Binds [list sign -|- * ::joingate::gate::on_sign]
    lappend Binds [list splt -|- * ::joingate::gate::on_splt]
    lappend Binds [list rejn -|- * ::joingate::gate::on_rejn]
    lappend Binds [list nick -|- * ::joingate::gate::on_nick]

    # Manual commands: op-only (o|o = global +o OR channel +o).
    foreach cmd {gatevoice gateblock gateallow gatesync} {
        lappend Binds [list pub o|o $cmd ::joingate::gate::pub_$cmd]
        lappend Binds [list dcc o|o $cmd ::joingate::gate::dcc_$cmd]
        lappend Binds [list msg o|o $cmd ::joingate::gate::msg_$cmd]
    }

    foreach b $Binds {
        bind {*}$b
    }

    if {![dict get $cfg enabled]} {
        ::joingate::irc::log "DISABLED. Gate logic inactive. Remove channel +m\
            in Ansible too, or the channel will be fully muted."
    } else {
        ::joingate::irc::log "loaded (channel [dict get $cfg channel],\
            [llength $Binds] binds, [llength [dict get $cfg rbl_providers]] RBL provider(s))"
    }
}

proc ::joingate::unload {} {
    variable Binds
    foreach b $Binds {
        catch {unbind {*}$b}
    }
    set Binds [list]
    # Kill every live soak / RBL / bootstrap timer so rehash fires nothing stale.
    ::joingate::cancel-all-timers
    set ::joingate::soak::Records [dict create]
    set ::joingate::soak::KeyTimers [dict create]
    variable RblPending; set RblPending [dict create]
    # Ephemeral trust overrides are cleared by design (FR-M5).
    namespace eval ::joingate::trust {
        variable Blocked [list]
        variable Allowed [list]
    }
}

::joingate::load

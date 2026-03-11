# $Id: QuoteEngine.tcl,v 1.9 2003/07/27 21:56:16 James Exp $

###############################################################################
# QuoteEngine for eggdrop bots
# Copyright (C) James Michael Seward 2003
#
# This program is covered by the GPL, please refer the to LICENCE file in the
# distribution.
###############################################################################

# load the extension
package require sqlite3

# path to SQLite database file (relative to eggdrop working dir)
set sql_db_path "data/quotedb/quotes.sqlite"

# bind commands
# CHANGE as needed (default is people with local +ov in bot)
bind pub "f" !addquote quote_add
bind pub "f" !quoteadd quote_add
bind pub "-" !randquote quote_rand
bind pub "-" !randauthor quote_by_author
bind pub "-" !quote quote_fetch
bind pub "-" !getquote quote_fetch
bind msg "-" !quote quote_fetch_msg
bind msg "-" !getquote quote_fetch_msg
bind pub "-" !titlesearch quote_search
bind pub "-" !searchtitle quote_search
bind pub "-" !searchtitles quote_search
bind pub "o" !delquote quote_delete
bind pub "o" !deletequote quote_delete
bind pub "-" !quotestats quote_stats
bind pub "-" !quoteinfo quote_info
bind pub "-" !quotever quote_version
bind pub "-" !quotehelp quote_help
bind pub "-" !quotesearch quote_content_search
bind pub "-" !searchquotes quote_content_search
bind pub "-" !searchquote quote_content_search

### code starts here
set quote_version "2.0.1"

# Open (or reopen on rehash) the persistent database handle and ensure schema exists
catch {quotes_db close}
sqlite3 quotes_db $sql_db_path
quotes_db eval {
  CREATE TABLE IF NOT EXISTS quotes (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    nick      TEXT,
    host      TEXT,
    title     TEXT UNIQUE,
    quote     TEXT,
    channel   TEXT,
    timestamp INTEGER
  )
}

proc quote_add {nick host handle channel text} {
    global quotes_db

    # Escape opening curly braces to prevent Tcl list parsing errors
    set text [regsub -all {\{} $text {\{}]

    if {($handle == "") || ($handle == "*")} {
        set handle $nick
    }

    set nick_host "$nick!$host"
    set title [string tolower [lindex $text 0]]
    set text [join [lrange $text 1 end]]

    if {$text == ""} {
        putserv "NOTICE $nick :Use: !addquote <title> <quote>"
        return 0
    }

    set ts [clock seconds]
    set sql {INSERT INTO quotes VALUES(NULL, $handle, $nick_host, $title, $text, $channel, $ts)}
    if {[catch {quotes_db eval $sql} err]} {
        if {[string match -nocase "*UNIQUE constraint failed: quotes.title*" $err]} {
            putserv "PRIVMSG $channel :Quote $title already exists."
        } else {
            putserv "PRIVMSG $channel :Error: $err"
        }
    } else {
        putserv "PRIVMSG $channel :Quote $title added."
    }
}


proc quote_rand {nick host handle channel text} {
    global quotes_db

    set found 0
    if {$text != ""} {
        set pattern "%[string trim $text]%"
        set sql {SELECT * FROM quotes WHERE channel=$channel
            AND (title LIKE $pattern OR quote LIKE $pattern)
            ORDER BY RANDOM() LIMIT 1}
        quotes_db eval $sql row {
      set found 1
    }
    } else {
        quotes_db eval {SELECT * FROM quotes WHERE channel=$channel ORDER BY RANDOM() LIMIT 1} row {
      set found 1
    }
    }

    if {$found} {
        putserv "PRIVMSG $channel :\002$row(title)\002: $row(quote)"
    } else {
        putserv "PRIVMSG $channel :No matches/quotes"
    }
}

proc quote_by_author {nick host handle channel text} {
    global quotes_db

    set found 0
    if {$text != ""} {
        set pattern "%[string trim $text]%"
        set sql {SELECT * FROM quotes WHERE channel=$channel
            AND nick LIKE $pattern ORDER BY RANDOM() LIMIT 1}
        quotes_db eval $sql row {
      set found 1
    }
    } else {
        quotes_db eval {SELECT * FROM quotes WHERE channel=$channel ORDER BY RANDOM() LIMIT 1} row {
      set found 1
    }
    }

    if {$found} {
        putserv "PRIVMSG $channel :\002$row(title)\002: $row(quote) :: Added by $row(nick)."
    } else {
        putserv "PRIVMSG $channel :No matches/quotes by this author"
    }
}

proc quote_fetch {nick host handle channel text} {
    global quotes_db

    if {$text == ""} {
        putserv "NOTICE $nick :Use: !quote <title>"
        return 0
    }

    if {[string length $text] > 50} {
        putserv "NOTICE $nick :Query too long."
        return 0
    }

    set text [string tolower [string trim $text]]
    set out ""
    quotes_db eval {SELECT * FROM quotes WHERE title=$text COLLATE NOCASE} row {
    if {$row(channel) != $channel} {
      set out "\002$row(title)\002: ($row(channel)) $row(quote)"
    } else {
      set out "\002$row(title)\002: $row(quote)"
    }
  }

    if {$out == ""} {
        set out "Couldn't find quote $text"
    }

    putserv "PRIVMSG $channel :$out"
}

proc quote_fetch_msg {nick host handle text} {
    global quotes_db

    if {$text == ""} {
        putserv "NOTICE $nick :Use: !quote <title>"
        return 0
    }

    if {[string length $text] > 50} {
        putserv "NOTICE $nick :Query too long."
        return 0
    }

    set text [string tolower [string trim $text]]
    set out ""
    quotes_db eval {SELECT * FROM quotes WHERE title=$text COLLATE NOCASE} row {
    set out "\002$row(title)\002: $row(quote)"
  }

    if {$out == ""} {
        set out "Couldn't find quote $text"
    }

    putserv "PRIVMSG $nick :$out"
}

proc quote_content_search {nick host handle channel text} {
    global quotes_db

    if {$text == ""} {
        putserv "NOTICE $nick :Usage: !searchquotes <text>"
        return 0
    }

    set pattern "%$text%"
    set titles {}
    quotes_db eval {SELECT title FROM quotes WHERE quote LIKE $pattern AND channel=$channel} row {
    lappend titles $row(title)
  }
    set num_rows [llength $titles]

    if {$num_rows > 0} {
        set count 0
        set result_string ""
        putserv "PRIVMSG $nick :Found $num_rows results"
        foreach qtitle $titles {
            if {$count == 10} {
                putserv "PRIVMSG $nick :$result_string"
                set result_string ""
                set count 0
            }
            append result_string "$qtitle "
            incr count
        }
        putserv "PRIVMSG $nick :$result_string"
    } else {
        putserv "PRIVMSG $nick :No results"
    }

    putserv "PRIVMSG $nick :End of search results"
}

proc quote_search {nick host handle channel text} {
    global quotes_db

    if {$text == ""} {
        putserv "NOTICE $nick :Usage: !findquote <text>"
        return 0
    }

    set pattern "%$text%"
    set titles {}
    quotes_db eval {SELECT title FROM quotes WHERE title LIKE $pattern AND channel=$channel} row {
    lappend titles $row(title)
  }
    set num_rows [llength $titles]

    if {$num_rows > 0} {
        set count 0
        set result_string ""
        putserv "PRIVMSG $nick :Found $num_rows results"
        foreach qtitle $titles {
            if {$count == 10} {
                putserv "PRIVMSG $nick :$result_string"
                set result_string ""
                set count 0
            }
            append result_string "$qtitle "
            incr count
        }
        putserv "PRIVMSG $nick :$result_string"
    } else {
        putserv "PRIVMSG $nick :No results"
    }

    putserv "PRIVMSG $nick :End of search results"
}

proc quote_stats {nick host handle channel text} {
    global quotes_db

    set total [lindex [quotes_db eval {SELECT COUNT(*) FROM quotes WHERE channel=$channel}] 0]
    set msg_total "The quotes database currently holds \002$total\002 quotes."

    set sql {SELECT COUNT(*) FROM quotes WHERE nick LIKE $handle AND channel=$channel}
    set by_handle [lindex [quotes_db eval $sql] 0]
    set msg_by_handle ""

    if {$by_handle > 0} {
        set msg_by_handle "You have added \002$by_handle\002 of them."
    }

    putserv "PRIVMSG $channel :$msg_total $msg_by_handle"
}

proc quote_info {nick host handle channel text} {
    global quotes_db

    set text [string tolower [string trim $text]]
    set found 0
    quotes_db eval {SELECT nick, timestamp FROM quotes WHERE title=$text COLLATE NOCASE} row {
    set found 1
  }

    if {$found} {
        set qtimestamp [clock format $row(timestamp) -format "%Y/%m/%d"]
        putserv "PRIVMSG $channel :Quote \002$text\002 was added by $row(nick) on \[$qtimestamp\]"
    } else {
        putserv "PRIVMSG $channel :Couldn't find quote $text"
    }
}

proc quote_delete {nick host handle channel text} {
    global quotes_db

    set text [string tolower [string trim $text]]
    if {![matchattr $handle m|m $channel]} {
        set sql {SELECT nick FROM quotes WHERE title=$text COLLATE NOCASE}
        set owner [lindex [quotes_db eval $sql] 0]
        if {$owner != $handle} {
            putserv "NOTICE $nick :You cannot delete that quote."
            return 0
        }
    }

    quotes_db eval {DELETE FROM quotes WHERE title=$text COLLATE NOCASE}
    if {[quotes_db changes] != 1} {
        putserv "PRIVMSG $channel :An error occurred deleting the quote."
        return 0
    } else {
        putserv "PRIVMSG $channel :Deleted quote $text"
    }
}

proc quote_version {nick host handle channel text} {
    global quote_version
    set msg "This is the QuoteEngine version $quote_version"
    append msg " adapted by TedSki, pwnage by bmatt, ruint by eck0"
    append msg " (original script written by JamesOff)"
    putserv "PRIVMSG $channel :$msg"
    return 0
}

proc quote_help {nick host handle channel text} {
    putserv "PRIVMSG $nick :Please listen to this entire message,\
        as our options have recently changed."
    putserv "PRIVMSG $nick :Commands for the QuoteEngine script: <req'd> \[optional\]"
    putserv "PRIVMSG $nick :  !addquote <title> <quote text> -\
        adds a quote to the database. Ops only."
    putserv "PRIVMSG $nick :  !delquote <title> - deletes a quote. Ops only."
    putserv "PRIVMSG $nick :  !randquote \[search text\] - fetches a random quote"
    putserv "PRIVMSG $nick :  !quote <title> - fetches the quote with <title>"
    putserv "PRIVMSG $nick :  !quoteinfo <title> - gets info about a quote"
    putserv "PRIVMSG $nick :  !titlesearch <text> - finds all quote titles containing 'text'"
    putserv "PRIVMSG $nick :  !quotesearch <text> - finds all quotes containing 'text'"
    putserv "PRIVMSG $nick :  !quotestats - get quote entry information"
    putserv "PRIVMSG $nick :  !quotever - get the version of the script"
    putserv "PRIVMSG $nick :  Some commands have synonyms and\
        spoonerisms: !getquote !deletequote !searchtitle"
    putserv "PRIVMSG $nick :  (End of help)"
    return 0
}

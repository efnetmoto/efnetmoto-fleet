bind pub "-" eck0: bots_maybe_broke

# Words we will match on.
set bb(bot_words) {
    bots
    bot's
    br0ts
    b0ts
    b0t's
}

set bb(broke_words) {
    broke
    br0ke
    broked
    br0ked
    broken
    br0ken
    borken
    b0rken
    fucked
}

# Characters we want to strip after the final word
set bb(strip_chars) ".,!"

# Do we want to only match if it is the first part of the line?
# eg: "eck0: b0t's broke" vs "eck0: wtf, the b0t's broke!"
set bb(match_first_only) 1

# What shall we kick them with?
set bb(kick_reason) "File a bug, n00b: https://github.com/efnetmoto/efnetmoto-fleet/issues"


proc bots_maybe_broke {nick host handle channel text} {
    global bb
    if {$text != ""} {
        set text [split [string tolower $text] " "]
        foreach word $text {
            set word_index [lsearch -exact $text $word]
            set first_match [lsearch -exact $bb(bot_words) $word]
            if {$first_match != -1} {
                # We are only looking for the first thing said to be about the bot.
                if {$bb(match_first_only) && ($word_index != 0)} {
                    return 0
                }
                # Find the next word after above, trim any punctuation and compare.
                set second_word [lindex $text [expr {$word_index + 1}]]
                set second_word [string trimright $second_word $bb(strip_chars)]
                set second_match [lsearch -exact $bb(broke_words) $second_word]
                if {$second_match != -1} {
                    putserv "KICK $channel $nick :$bb(kick_reason)"
                }
            }
        }
    }
}

#!/bin/sh

# Generated PDFs are written next to this script, regardless of the caller's cwd.
script_dir=$(cd "$(dirname "$0")" && pwd)

. "$script_dir/make_barcodes.sh"

# Work order actions
make_sheet "" "$script_dir/barcodes_actions_Manufacturing.pdf" \
"START/PAUSE
OBTPAUS
OBTPAUS

VALIDATE/NEXT
OBTNEXT
OBTNEXT

PREVIOUS
OBTPREV
OBTPREV

SKIP
OBTSKIP
OBTSKIP

MARK AS DONE
OBTCLWO
OBTCLWO

CLOSE PRODUCTION
OBTCLMO
OBTCLMO

PASS
OBTPASS
OBTPASS

FAIL
OBTFAIL
OBTFAIL

RECORD PRODUCTION
OBTRECO
OBTRECO

PRINT LABEL
OBTPRPL
OBTPRPL
"

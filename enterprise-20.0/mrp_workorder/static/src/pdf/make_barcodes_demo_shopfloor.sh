#!/bin/sh

# Generated PDFs are written next to this script, regardless of the caller's cwd.
script_dir=$(cd "$(dirname "$0")" && pwd)

. "$script_dir/make_barcodes.sh"

# Shop Floor Demo Sheet 1
make_sheet "Login and validate work orders" "$script_dir/barcodes_demo_shopfloor_sheet1.pdf" \
"Scan Employee Badge
041517863199
041517863199 - Ernest Reed

Scan Manufacturing Order
WH/MO/DEMO1
WH/MO/DEMO1

Select Work Center
drill1
drill1 - Drill 1

Start Work Order
OBTPAUS
OBTPAUS

Pause Work Order
OBTPAUS
OBTPAUS

Mark As Done
OBTCLWO
OBTCLWO

Select Work Center
assembly1
assembly1 - Assembly 1

Scan Manufacturing Order
WH/MO/DEMO1
WH/MO/DEMO1

Mark As Done
OBTCLWO
OBTCLWO

Scan Manufacturing Order
WH/MO/DEMO1
WH/MO/DEMO1

Close Production
OBTCLMO
OBTCLMO
"

# Shop Floor Demo Sheet 2
make_sheet "Consume components and validate production" "$script_dir/barcodes_demo_shopfloor_sheet2.pdf" \
"Scan Work Center
drill1
drill1 - Drill 1

Scan Manufacturing Order
WH/MO/DEMO2
WH/MO/DEMO2

Scan Product
601647855646
601647855646 - Drawer Black - FURN_2100

Scan Lot Number
0000000010001
0000000010001

Scan Product
601647855647
601647855647 - Drawer Case Black - FURN_5623

Scan Lot Number
0000000020045
0000000020045

Mark As Done
OBTCLWO
OBTCLWO

Select Work Center
assembly1
assembly1 - Assembly 1

Scan Manufacturing Order
WH/MO/DEMO2
WH/MO/DEMO2

Mark As Done
OBTCLWO
OBTCLWO

Scan Manufacturing Order
WH/MO/DEMO2
WH/MO/DEMO2

Close Production
OBTCLMO
OBTCLMO
"

# Merge the two sheets into a single PDF
gs -q -dNOPAUSE -dBATCH -sDEVICE=pdfwrite -sOutputFile="$script_dir/barcodes_demo_shopfloor.pdf" \
    "$script_dir/barcodes_demo_shopfloor_sheet1.pdf" "$script_dir/barcodes_demo_shopfloor_sheet2.pdf"
rm "$script_dir/barcodes_demo_shopfloor_sheet1.pdf" "$script_dir/barcodes_demo_shopfloor_sheet2.pdf"

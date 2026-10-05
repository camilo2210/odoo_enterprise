#!/bin/sh

barcode -t 2x7+40+40 -m 50x30 -p "210x297mm" -e code128b -n > barcodes_actions_barcode.ps << BARCODES
OCDMENU
OCDDISC
OBTVALI
OCDCANC
OBTPROP
OBTPRSL
OBTPACK
OBTUPCK
OBTSCRA
OBTRECO
OBTRETU
OBTWREV
BARCODES

cat > barcodes_actions_header.ps << HEADER
%!PS
/showTitle { /Helvetica findfont 12 scalefont setfont moveto show } def
(MAIN MENU) 89 768 showTitle
(DISCARD) 348 768 showTitle
(VALIDATE) 89 660 showTitle
(CANCEL) 348 660 showTitle
(PRINT PICKING OPERATION) 89 551 showTitle
(PRINT DELIVERY SLIP) 348 551 showTitle
(PUT IN PACK) 89 444 showTitle
(UNPACK) 348 444 showTitle
(SCRAP) 89 337 showTitle
(RECORD COMPONENTS) 348 337 showTitle
(RETURN) 89 230 showTitle
(WAIT A REVIEW) 348 230 showTitle
HEADER

cat barcodes_actions_header.ps barcodes_actions_barcode.ps | ps2pdf - - > barcodes_actions.pdf
rm barcodes_actions_header.ps barcodes_actions_barcode.ps

# pg 1 of demo barcodes due to ps headers being restricted to 1 page. Some blanks may exist due to flows having a rows with less than 3 barcodes.
barcode -t 3x7+20+70 -m 25x30 -p "210x297mm" -e code128b -n > barcodes_demo_barcode_pg_1.ps  << BARCODES
WHIN
6016478556387
OBTVALI
WH/OUT/00005
6016478556448
OBTVALI
WHIN
6016478556400
6016478556318
LOT-000002
LOT-000003
OBTVALI
WHSTOCK
6016478556493
SHELF1
OBTVALI
BARCODES

# blank lines included for easier visual matching to barcode spacing
cat > barcodes_demo_header_pg_1.ps << HEADER
%!PS
/showLabel { /Helvetica findfont 14 scalefont setfont moveto show } def
/showTitle { /Helvetica findfont 11 scalefont setfont moveto show } def
/showCode { /Helvetica findfont 8 scalefont setfont moveto show } def
/showFooter { /Helvetica findfont 8 scalefont setfont moveto show } def

(Receive products in stock) 45 767 showLabel
(YourCompany Receipts) 45 747 showTitle
(WHIN) 85 688 showCode
(Desk Stand with Screen) 230 747 showTitle
(6016478556387) 271 688 showCode
(Validate) 415 747 showTitle
(OBTVALI) 456 688 showCode

(Deliver products to your customers) 45 6292 showLabel
(WH/OUT/00005) 45 642 showTitle
(WH/OUT/00005) 85 590 showCode
(Desk Combination) 230 642 showTitle
(6016478556448) 271 590 showCode
(Validate) 415 642 showTitle
(OBTVALI) 456 590 showCode

(Receive products tracked by lot number (activate Lots & Serial Numbers)) 45 560 showLabel
(YourCompany Receipts) 45 544 showTitle
(WHIN) 85 492 showCode
(Corner Desk Black) 230 544 showTitle
(6016478556400) 271 492 showCode
(Cable Management Box) 415 544 showTitle
(6016478556318) 456 492 showCode
(LOT-000002) 45 446 showTitle
(LOT-000002) 85 392 showCode
(LOT-000003) 230 446 showTitle
(LOT-000003) 271 392 showCode
(Validate) 415 446 showTitle
(OBTVALI) 456 392 showCode

(Internal transfer (activate Storage Locations)) 45 362 showLabel
(WH/Stock) 45 346 showTitle
(WHSTOCK) 85 292 showCode
(Pedal Bin) 230 346 showTitle
(6016478556493) 271 292 showCode
(WH/Stock/Shelf1) 415 346 showTitle
(SHELF1) 456 292 showCode
(Validate) 45 243 showTitle
(OBTVALI) 85 189 showCode

(Don't have any barcode scanner? Right click on your screen > Inspect > Console and type the following command:) 45 35 showFooter
(   odoo.__WOWL_DEBUG__.root.env.services.barcode.bus.trigger("barcode_scanned", {barcode:"setyourbarcodehere"})) 45 25 showFooter
(and replace "setyourbarcodehere" by the barcode you would like to scan OR use our mobile app.) 45 15 showFooter
HEADER

# pg 2 of demo barcodes. Some blanks may exist due to flows having a rows with less than 3 barcodes.
barcode -t 3x7+20+70 -m 25x30 -p "210x297mm" -e code128b -n > barcodes_demo_barcode_pg_2.ps  << BARCODES
WHIN
6016478556509
OBTPACK
OBTVALI


WH/IN/00009
PAL0000001
OBTVALI
BARCODES

cat > barcodes_demo_header_pg_2.ps << HEADER
%!PS
/showLabel { /Helvetica findfont 14 scalefont setfont moveto show } def
/showTitle { /Helvetica findfont 11 scalefont setfont moveto show } def
/showCode { /Helvetica findfont 8 scalefont setfont moveto show } def
/showFooter { /Helvetica findfont 8 scalefont setfont moveto show } def

(Put in Pack (activate Packages)) 45 765 showLabel
(YourCompany Receipts) 45 747 showTitle
(WHIN) 85 688 showCode
(Large Cabinet) 230 747 showTitle
(6016478556509) 271 688 showCode
(Put in Pack) 415 747 showTitle
(OBTPACK) 456 688 showCode
(Validate) 45 642 showTitle
(OBTVALI) 85 590 showCode

(Receive products inside packages) 45 560 showLabel
(WH/IN/00009) 45 544 showTitle
(WH/IN/00009) 85 492 showCode
(PAL0000001) 230 544 showTitle
(PAL0000001) 271 492 showCode
(Validate) 415 544 showTitle
(OBTVALI) 456 492 showCode

(Don't have any barcode scanner? Right click on your screen > Inspect > Console and type the following command:) 45 35 showFooter
(   odoo.__WOWL_DEBUG__.root.env.services.barcode.bus.trigger("barcode_scanned", {barcode:"setyourbarcodehere"})) 45 25 showFooter
(and replace "setyourbarcodehere" by the barcode you would like to scan OR use our mobile app.) 45 15 showFooter
HEADER

# pg 3 of demo barcodes. Some blanks may exist due to flows having a rows with less than 3 barcodes.
barcode -t 3x7+20+70 -m 25x30 -p "210x297mm" -e code128b -n > barcodes_demo_barcode_pg_3.ps  << BARCODES
BATCH/OUT/00002
6016478556420
6016478556516
6016478556356
OBTVALI

BATCH/OUT/00001
6016478556530
6016478556523
SN-000007
SN-000008
CLUSTER-PACK-1
6016478556516
CLUSTER-PACK-2
OBTVALI
BARCODES

cat > barcodes_demo_header_pg_3.ps << HEADER
%!PS
/showLabel { /Helvetica findfont 14 scalefont setfont moveto show } def
/showTitle { /Helvetica findfont 11 scalefont setfont moveto show } def
/showCode { /Helvetica findfont 8 scalefont setfont moveto show } def
/showFooter { /Helvetica findfont 8 scalefont setfont moveto show } def

(Batch picking (activate Batch Pickings)) 45 767 showLabel
(BATCH/OUT/00002) 45 747 showTitle
(BATCH/OUT/00002) 85 688 showCode
(Large Meeting Table) 230 747 showTitle
(6016478556420) 271 688 showCode
(Four Person Desk) 415 747 showTitle
(6016478556516) 456 688 showCode
(Three-Seat Sofa) 45 642 showTitle
(6016478556356) 85 590 showCode
(Validate) 230 642 showTitle
(OBTVALI) 271 590 showCode

(Batch picking with cluster pickings (activate Batch Pickings and Packages)) 45 560 showLabel
(BATCH/OUT/00001) 45 544 showTitle
(BATCH/OUT/00001) 85 492 showCode
(Acoustic Bloc Screens) 230 544 showTitle
(6016478556530) 271 492 showCode
(Cabinet with Doors) 415 544 showTitle
(6016478556523) 456 492 showCode
(SN-000007) 45 446 showTitle
(SN-000007) 85 392 showCode
(SN-000008) 230 446 showTitle
(SN-000008) 271 392 showCode
(CLUSTER-PACK-1) 415 446 showTitle
(CLUSTER-PACK-1) 456 392 showCode
(Four Person Desk) 45 346 showTitle
(6016478556516) 85 292 showCode
(CLUSTER-PACK-2) 230 346 showTitle
(CLUSTER-PACK-2) 271 292 showCode
(Validate) 415 346 showTitle
(OBTVALI) 456 292 showCode

(Don't have any barcode scanner? Right click on your screen > Inspect > Console and type the following command:) 45 35 showFooter
(   odoo.__WOWL_DEBUG__.root.env.services.barcode.bus.trigger("barcode_scanned", {barcode:"setyourbarcodehere"})) 45 25 showFooter
(and replace "setyourbarcodehere" by the barcode you would like to scan OR use our mobile app.) 45 15 showFooter
HEADER
cat barcodes_demo_header_pg_1.ps barcodes_demo_barcode_pg_1.ps barcodes_demo_header_pg_2.ps barcodes_demo_barcode_pg_2.ps barcodes_demo_header_pg_3.ps barcodes_demo_barcode_pg_3.ps | ps2pdf - - > barcodes_demo.pdf
rm barcodes_demo_header_pg_1.ps barcodes_demo_barcode_pg_1.ps
rm barcodes_demo_header_pg_2.ps barcodes_demo_barcode_pg_2.ps
rm barcodes_demo_header_pg_3.ps barcodes_demo_barcode_pg_3.ps

python3 make_barcodes.py

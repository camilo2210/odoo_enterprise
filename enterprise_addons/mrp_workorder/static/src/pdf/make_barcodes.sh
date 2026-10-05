#!/bin/sh

# Generated PDFs are written next to this script, regardless of the caller's cwd.
script_dir=$(cd "$(dirname "$0")" && pwd)

# make_sheet <sheet title> <output.pdf> <cells>
#
# <cells> is a sequence of 3-line groups, one per barcode, in the order they
# should appear on the page (first_row/col1, first_row/col2, row2/col1, ...; always 2
# columns):
#   <label shown above the barcode>
#   <value actually encoded in the barcode>
#   <text shown below the barcode>
#
# Known limitations:
# We can't skip a cell, so if you want to have a single barcode on a row, you need to put a dummy barcode in the other column.
# Over 7 rows, barcodes will print out of the page. If you want to have more than 7 rows, you need to create multiple sheets.
# If you don't exactly set 3 values per cell, values will be misaligned. The script does not check for this.
make_sheet () {
    sheet_title=$1
    out=$2
    cells=$3
    center_vertically=${4:-false}
    blank_middle_column=${5:-false}


    printf '%s\n' "$cells" | grep . > cells_TMP_FILE
    if [ "$blank_middle_column" = "true" ]; then
        columns=3
        cell_inner_margin="22x30"
    else
        columns=2
        cell_inner_margin="66x30"
    fi
    n_cells=$(wc -l < cells_TMP_FILE)
    n_cells=$(( n_cells / 3 ))
    rows=$(( (n_cells + 1) / 2 ))
    if [ "$center_vertically" = "false" ]; then
        rows=$(( rows < 7 ? 7 : rows )) # We could set 7 as a constant but we allow the user to mess up...
    fi

    # marginV keeps the row spacing identical.
    marginV=$(( (842 - 108 * rows) / 2 ))

    # A 3-column grid (real, blank, real) instead of 2 is what lets the
    # blank middle column soak up extra space without also pushing the
    # outer margins out.
    if [ "$blank_middle_column" = "true" ]; then x_left=62; else x_left=106; fi
    if [ "$blank_middle_column" = "true" ]; then x_right=404; else x_right=363; fi
    # y of 1st row title; each next row is 108pt lower.
    y_first_row=$(( 396 + 54 * rows ))

    barcodes=""
    headers=""
    idx=0
    while IFS= read -r cell_label && IFS= read -r cell_barcode && IFS= read -r cell_value; do
        row=$(( idx / 2 )) # 0 based
        if [ $(( idx % 2 )) -eq 0 ]; then x=$x_left; else x=$x_right; fi
        title_y=$(( y_first_row - 108 * row ))
        value_y=$(( title_y - 64 ))

        if [ -z "$barcodes" ]; then
            barcodes="$cell_barcode"
        else
            barcodes="$barcodes
$cell_barcode"
        fi
        # blank 3rd (middle) column of this row, right after its left cell.
        if [ "$blank_middle_column" = "true" ] && [ $(( idx % 2 )) -eq 0 ]; then
            barcodes="$barcodes
"
        fi
        headers="$headers
($cell_label) $x $title_y showTitle
($cell_value) $x $value_y showValue"

        idx=$(( idx + 1 ))
    done < cells_TMP_FILE
    rm cells_TMP_FILE

    barcode -t ${columns}x${rows}+40+${marginV} -m ${cell_inner_margin} -p "210x297mm" -e code128b -n -o barcodes_TMP_FILE.ps << BARCODES
$barcodes
BARCODES

    cat > barcodesHeaders_TMP_FILE.ps << HEADER
/showTitle { /Helvetica-Bold findfont 12 scalefont setfont moveto show } def
/showValue { /Helvetica findfont 10 scalefont setfont moveto show } def
/showSheetTitle { /Helvetica-Bold findfont 16 scalefont setfont moveto show } def
($sheet_title) $x_left 810 showSheetTitle
$headers
HEADER

    cat barcodesHeaders_TMP_FILE.ps barcodes_TMP_FILE.ps | ps2pdf -sPAPERSIZE=a4 - "$out"
    rm barcodesHeaders_TMP_FILE.ps barcodes_TMP_FILE.ps
}

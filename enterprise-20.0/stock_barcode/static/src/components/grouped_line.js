import LineComponent from "@stock_barcode/components/line";

export default class GroupedLineComponent extends LineComponent {
    static components = { LineComponent };
    static template = "stock_barcode.GroupedLineComponent";

    get isComplete() {
        if (
            this.linesToDisplay.length > 1 &&
            this.isTracked &&
            this.qtyDemand &&
            this.qtyDone === this.qtyDemand
        ) {
            // In case the line is tracked and has multiple sublines, we consider the line complete
            // if it has enough quantity and all sublines with quantity has a lot.
            for (const subline of this.linesToDisplay) {
                const lotName = subline.lot_id?.name || subline.lot_name;
                if (this.env.model.getQtyDone(subline) && !lotName) {
                    return false;
                }
            }
            return true;
        }
        return super.isComplete;
    }

    get isSelected() {
        return this.line.virtual_ids.indexOf(this.env.model.selectedLineVirtualId) !== -1;
    }

    get opened() {
        return this.env.model.groupKey(this.line) === this.env.model.unfoldLineKey;
    }

    getsublineProps(subline) {
        const sublineProps = {
            displayUOM: this.props.displayUOM,
            editLine: this.props.editLine,
            line: subline,
            subline: true,
        };
        if (this.env.model.resModel === "stock.picking.batch") {
            // Don't display the picking on sublines if already displayed on grouped line.
            sublineProps.hidePickingName = Boolean(this.pickingName);
        }
        return sublineProps;
    }

    get linesToDisplay() {
        if (this.env.model.resModel === "stock.picking.batch" && !this.pickingName) {
            return this.props.line.lines;
        }
        if (!this.env.model.showReservedSns) {
            return this.props.line.lines.filter(
                (line) =>
                    this.env.model.getQtyDone(line) > 0 ||
                    !["lot", "serial"].includes(line.product_id.tracking) ||
                    this.env.model.getQtyDemand(line) == 0
            );
        }
        return this.props.line.lines;
    }

    get lotName() {
        if (!this.env.model.showReservedSns) {
            // In case we don't display unscanned reserved lots, display it only
            // if only one subline with a lot has some quantity done.
            if (this.linesToDisplay.length === 1) {
                for (const line of this.linesToDisplay) {
                    const lotName = line.lot_id?.name || line.lot_name;
                    if (lotName && this.env.model.getQtyDone(this.line)) {
                        return lotName;
                    }
                }
            } else {
                return "";
            }
        }
        return super.lotName;
    }

    get mainSubLine() {
        // In case we don't display unscanned reserved lots, this util can be
        // used to record the data of the unique relevant representant.
        if (!this.env.model.showReservedSns && this.linesToDisplay.length === 1) {
            const line = this.linesToDisplay[0];
            if (this.env.model.getQtyDone(line) && (line.package_id || line.result_package_id)) {
                return line;
            }
        }
        return false;
    }

    get displayToggleBtn() {
        if (this.env.model.resModel === "stock.picking.batch" && !this.pickingName) {
            return true;
        }
        return this.linesToDisplay.length > 1;
    }

    toggleSublines(ev) {
        ev.stopPropagation();
        this.env.model.toggleSublines(this.line);
    }
}

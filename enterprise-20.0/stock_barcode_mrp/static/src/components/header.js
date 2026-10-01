import { Component, t, useProps } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

export default class HeaderComponent extends Component {
    static template = "stock_barcode_mrp.HeaderComponent";

    props = useProps({
        displayUOM: t.any(),
        openDetails: t.any(),
        line: t.any(),
    });

    get line() {
        return this.props.line;
    }

    get displayGenerateSerialButton() {
        if (this.isTracked) {
            const { tracking } = this.order.product_id;
            if (tracking === "lot") {
                return this.isTracked && !this.lotName;
            } else if (tracking === "serial") {
                return (this.order.lot_producing_ids?.length || 0) < this.qtyDemand;
            }
        }
        return false;
    }

    get order() {
        return this.env.model.record;
    }

    get qtyDemand() {
        return this.order.product_qty;
    }

    get incrementQty() {
        return Math.max(this.order.product_qty - this.order.qty_producing, 0);
    }

    get qtyDone() {
        return this.order.qty_producing;
    }

    get isTracked() {
        return ["lot", "serial"].includes(this.order.product_id.tracking);
    }

    get lotName() {
        if (this.order.lot_producing_ids.length) {
            const serialNames = this.order.lot_producing_ids.map((sn) => sn.name);
            if (serialNames.length > 5) {
                // Too many serial numbers, display the three firsts and the last one instead.
                return _t("%(firstSN)s, %(secondSN)s, %(thirdSN)s, …, %(lastSN)s", {
                    firstSN: serialNames[0],
                    secondSN: serialNames[1],
                    thirdSN: serialNames[2],
                    lastSN: serialNames.pop(),
                });
            }
            return serialNames.join(", ");
        }
        return this.order.lot_name || "";
    }

    get isComplete() {
        return this.env.model.isComplete;
    }

    get componentClasses() {
        return this.isComplete ? "o_header_completed" : "";
    }

    get hideProduceButton() {
        return this.incrementQty === 0;
    }

    get isSelected() {
        return true;
    }

    get productionPackageLabels() {
        const moveLineIds = this.order.finished_move_line_ids;
        const byProductLineIds = this.order.move_byproduct_line_ids;
        const finalProductLineIds = moveLineIds
            .filter((id) => !byProductLineIds.includes(id))
            .sort((id1, id2) => id1 - id2);
        const packageLabels = [];
        let hasPackage = false;
        for (const id of finalProductLineIds) {
            const moveLine = this.env.model.cache.getRecord("stock.move.line", id, false);
            const packageId = moveLine?.result_package_id;
            if (!packageId) {
                packageLabels.push(_t("No Package"));
                continue;
            }
            const resultPackage = this.env.model.cache.getRecord("stock.package", packageId, false);
            if (resultPackage) {
                packageLabels.push(resultPackage.dest_complete_name);
                hasPackage = true;
            }
        }
        if (!hasPackage) {
            return [];
        }
        return packageLabels;
    }
}

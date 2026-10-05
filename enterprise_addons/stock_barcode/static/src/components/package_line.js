import { t } from "@odoo/owl";
import LineComponent from "./line";

export default class PackageLineComponent extends LineComponent {
    static template = "stock_barcode.PackageLineComponent";
    static propsSchema = {
        displayUOM: t.any(),
        line: t.any(),
        openPackage: t.any(),
    };

    get isComplete() {
        return this.qtyDemand ? this.qtyDone == this.qtyDemand : this.qtyDone > 0;
    }

    get isSelected() {
        return this.line.package_id.id === this.env.model.lastScanned.packageId;
    }

    get qtyDemand() {
        return this.props.line.reserved_uom_qty ? 1 : 0;
    }

    get qtyDone() {
        const reservedQuantity = this.line.lines.reduce((r, l) => r + l.reserved_uom_qty, 0);
        const doneQuantity = this.line.lines.reduce((r, l) => r + l.qty_done, 0);
        if (reservedQuantity > 0) {
            return doneQuantity / reservedQuantity;
        }
        return doneQuantity > 0 ? 1 : 0;
    }

    get packageDataAttribute() {
        return this.hasSameSourceAndResultPackage()
            ? this.line.package_id.parent_package_id.name
            : this.line.package_id.name;
    }

    get packageLabel() {
        return this.hasSameSourceAndResultPackage()
            ? this.line.package_id.parent_package_id.name
            : super.packageLabel;
    }

    get resultPackageLabel() {
        return this.hasSameSourceAndResultPackage()
            ? this.line.outermost_result_package_id.name
            : super.resultPackageLabel;
    }

    hasSameSourceAndResultPackage() {
        if (this.line.package_id.parent_package_id && this.line.outermost_result_package_id) {
            // Need to recompute the result package "complete_name" since it is not recomputed when unpack.
            const currentResultFullPackageName = `${this.line.outermost_result_package_id.name} > ${this.line.result_package_id.name}`;
            if (this.line.package_id.complete_name === currentResultFullPackageName) {
                return true;
            }
        }
        return false;
    }

    delete(ev) {
        ev.stopPropagation();
        this.env.model.deleteLines(this.line.lines);
        this.env.model.trigger("update");
    }

    select(ev) {
        ev.stopPropagation();
        this.env.model.selectPackageLine(this.line);
        this.env.model.trigger("update");
    }

    openPackage() {
        let packageIds = [this.line.package_id.id];
        if (this.line.lines) {
            packageIds = Array.from(new Set(this.line.lines.map((line) => line.package_id.id)));
        }
        return this.props.openPackage(packageIds);
    }

    async unpack() {
        await this.env.model.unpack(this.line.lines);
    }
}

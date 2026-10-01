import { Component, onMounted, onWillStart, signal, t, useOnChange, useProps } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";
import { parseInteger } from "@web/views/fields/parsers";
import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";

export class BarcodeGenerateDialog extends Component {
    static template = "stock_barcode.barcode_generate_snln_dialog";
    static components = { Dialog };

    props = useProps({
        model: t.object(),
        move: t.object(),
        line: t.object(),
        nextCustomSerialNumber: t.string(),
        close: t.function(),
    });

    nextSerial = signal.ref();
    nextSerialCount = signal.ref();
    totalReceived = signal.ref();

    setup() {
        this.orm = useService("orm");
        this.isLotTracking = this.props.line.product_id.tracking === "lot";
        this.title = this.isLotTracking
            ? _t("Generate Lot numbers")
            : _t("Generate Serial numbers");
        this.generationMode = signal(
            this.props.model.pickingTypeId.barcode_default_snln_generation
        );

        onWillStart(async () => {
            this.displayUOM = await user.hasGroup("uom.group_uom");
        });

        onMounted(async () => {
            this.nextSerial().value = this.props.nextCustomSerialNumber;
            this._onChangeGenerationMode(this.generationMode());
            this.nextSerial()?.focus();
        });

        useOnChange(
            () => [this.generationMode()],
            (value) => this._onChangeGenerationMode(value)
        );
    }

    async _onValidate() {
        const count = parseInteger(this.nextSerialCount()?.value || "0");
        const qtyToProcess =
            this.generationMode() === "only_one" && !this.isLotTracking
                ? 1
                : parseInt(this.totalReceived()?.value || this.props.move.product_uom_qty);

        const moveLineVals = await this.orm.call("stock.move", "action_generate_lot_line_vals", [
            {
                default_product_id: this.props.move.product_id,
                default_location_dest_id: this.props.move.location_dest_id,
                default_location_id: this.props.move.location_id,
                default_tracking: this.props.move.has_tracking,
                default_quantity: qtyToProcess,
                default_uom_id: this.isLotTracking ? this.props.move.uom_id : undefined,
            },
            "generate",
            this.nextSerial()?.value,
            count,
            "",
        ]);
        const lines = this.props.model.pageLines.filter((l) =>
            this.props.move.move_line_ids.includes(l.id)
        );
        const lineToUpdate = lines.filter((l) => !l.lot_name);
        let i = 0;
        while (i < lineToUpdate.length && i < moveLineVals.length) {
            const vals = moveLineVals[i];
            await this.props.model.updateLine(lineToUpdate[i], {
                lot_name: vals.lot_name,
                qty_done: vals.quantity,
            });
            i += 1;
        }

        while (i < moveLineVals.length) {
            const vals = moveLineVals[i];
            await this.props.model.createNewLine({
                copyOf: lines[0],
                fieldsParams: {
                    lot_name: vals.lot_name,
                    qty_done: vals.quantity,
                },
            });
            i += 1;
        }
        const pickingType = this.props.model.pickingTypeId;
        this.props.model.cache.setCache({
            "stock.picking.type": [
                {
                    ...pickingType,
                    barcode_default_snln_generation: this.generationMode(),
                },
            ],
        });
        this.orm.write("stock.picking.type", [pickingType.id], {
            barcode_default_snln_generation: this.generationMode(),
        });
        this.props.model.trigger("update");
        this.props.close();
    }

    _onChangeGenerationMode(value) {
        if (this.nextSerialCount()) {
            if (!this.isLotTracking && value === "only_one") {
                this.nextSerialCount().value = 1;
            } else {
                this.nextSerialCount().value =
                    this.props.model.getIncrementQuantity(this.props.line) || 2;
            }
        }
        if (this.totalReceived()) {
            this.totalReceived().value =
                this.props.model.getIncrementQuantity(this.props.line) || 2;
        }
    }
}

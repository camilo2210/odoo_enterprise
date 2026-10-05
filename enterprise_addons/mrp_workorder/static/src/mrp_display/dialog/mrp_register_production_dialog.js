import { useService } from "@web/core/utils/hooks";
import { formatFloat } from "@web/views/fields/formatters";
import {
    ConfirmationDialog,
    confirmationDialogProps,
} from "@web/core/confirmation_dialog/confirmation_dialog";
import { FloatField } from "@web/views/fields/float/float_field";
import { Many2ManyTagsField } from "@web/views/fields/many2many_tags/many2many_tags_field";
import { onWillStart, useProps, proxy, t } from "@odoo/owl";

export class MrpRegisterProductionDialog extends ConfirmationDialog {
    static template = "mrp_workorder.MrpRegisterProductionDialog";
    props = useProps({
        ...confirmationDialogProps,
        qtyToProduce: t.number().optional(),
        record: t.object(),
        reload: t.function(),
        workorder: t.object().optional(),
    });
    static components = {
        ...ConfirmationDialog.components,
        FloatField,
        Many2ManyTagsField,
    };

    setup() {
        super.setup();
        if (this.props.qtyToProduce) {
            this.quantityToProduce = this.props.qtyToProduce;
        } else {
            this.quantityToProduce = this.props.record.data.product_qty;
        }
        this.formatFloat = formatFloat;
        this.state = proxy({ disabled: false });
        onWillStart(async () => {
            if (
                ["lot", "serial"].includes(this.props.record.data.product_tracking) &&
                !this.props.record.data.lot_producing_ids.count
            ) {
                await this.props.record.load();
            }
        });
        this.actionService = useService("action");
    }

    async validate() {
        this.state.disabled = true;
        await this.props.record.save();
        await this.props.workorder?.save();
        const record = this.props.workorder ? this.props.workorder : this.props.record;
        await record.model.orm.call(record.resModel, "set_qty_producing", [record.resId]);
        await this.props.reload(this.props.record);
        this.props.close();
    }

    async actionGenerateSerial() {
        await this.props.record.save();
        const action = await this.props.record.model.orm.call(
            this.props.record.resModel,
            "action_generate_serial",
            [this.props.record.resId]
        );
        if (action && typeof action === "object") {
            return this.actionService.doAction(action, {
                onClose: () => {
                    this.props.reload(this.props.record);
                },
            });
        }
        await this.props.reload(this.props.record);
    }

    async actionClearLotProducing() {
        await this.props.record.model.orm.call(
            this.props.record.resModel,
            "action_clear_lot_producing_ids",
            [this.props.record.resId]
        );
        await this.props.reload(this.props.record);
    }

    get lotInfo() {
        const { product_id, company_id } = this.props.record.data;
        return {
            name: "lot_producing_ids",
            record: this.props.record,
            context: {
                default_product_id: product_id.id,
                default_company_id: company_id.id,
            },
            domain: [
                "&",
                ["product_id", "=", product_id.id],
                "|",
                ["company_id", "=", false],
                ["company_id", "=", company_id.id],
            ],
        };
    }

    get qtyDoneInfo() {
        if (this.props.workorder) {
            return {
                name: "qty_produced",
                record: this.props.workorder,
            };
        }
        return {
            name: "qty_producing",
            record: this.props.record,
        };
    }
}

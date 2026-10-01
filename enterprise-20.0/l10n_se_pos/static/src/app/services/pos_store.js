import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { SwedenBlackboxError } from "@l10n_se_pos/app/errors/error_handlers";
const { DateTime } = luxon;

patch(PosStore.prototype, {
    async setup() {
        await super.setup(...arguments);
        this.ticketPrinter.pos = this;
    },
    useBlackBoxSweden() {
        return !!this.config.iot_fdm_se_id;
    },
    hasNegativeAndPositiveProducts(product) {
        const isPositive = product.list_price >= 0;
        const order = this.getOrder();

        for (const id in order.getOrderlines()) {
            const line = order.getOrderlines()[id];
            if (
                (line.product_id.list_price >= 0 && !isPositive) ||
                (line.product_id.list_price < 0 && isPositive)
            ) {
                return true;
            }
        }
        return false;
    },
    async addLineToCurrentOrder(vals, opt = {}, configure = true) {
        const product = vals.product_tmpl_id;
        const productTaxesIds = product.taxes_id.map((tax) => tax.id);
        if (this.useBlackBoxSweden() && product.taxes_id.length === 0) {
            this.dialog.add(AlertDialog, {
                title: _t("Oh snap !"),
                body: _t(
                    "It seems that no tax is set on the product. Please check it's configuration."
                ),
            });
            return;
        } else if (
            this.useBlackBoxSweden() &&
            !this.models["account.tax"]
                .filter((tax) => productTaxesIds.includes(tax.id))
                ?.every((tax) => tax.tax_group_id.pos_receipt_label)
        ) {
            this.dialog.add(AlertDialog, {
                title: _t("Oh snap !"),
                body: _t(
                    "Product has an invalid tax amount. Only 25%, 12%, 6% and 0% are allowed."
                ),
            });
            return;
        } else if (this.useBlackBoxSweden() && this.getOrder().lines.find((l) => l.is_return)) {
            this.dialog.add(AlertDialog, {
                title: _t("Oh snap !"),
                body: _t("Cannot modify a refund order."),
            });
            return;
        } else if (this.useBlackBoxSweden() && this.hasNegativeAndPositiveProducts(product)) {
            this.dialog.add(AlertDialog, {
                title: _t("Oh snap !"),
                body: _t("You can only make positive or negative order. You cannot mix both."),
            });
            return;
        } else {
            return await super.addLineToCurrentOrder(vals, opt, configure);
        }
    },
    disallowLineQuantityChange() {
        const result = super.disallowLineQuantityChange(...arguments);
        return this.useBlackBoxSweden() || result;
    },
    async preSyncAllOrders(orders) {
        if (this.useBlackBoxSweden() && orders.length > 0) {
            for (const order of orders) {
                await this.pushSingleOrder(order);
            }
        }
        return super.preSyncAllOrders(orders);
    },
    async pushSingleOrder(order) {
        if (this.useBlackBoxSweden() && order) {
            if (!order.receipt_type) {
                order.receipt_type = "normal";
                order.sequence_number = await this.getOrderSequenceNumber();
            }
            try {
                order.sweden_blackbox_tax_category_a = order.getSpecificTax("A");
                order.sweden_blackbox_tax_category_b = order.getSpecificTax("B");
                order.sweden_blackbox_tax_category_c = order.getSpecificTax("C");
                order.sweden_blackbox_tax_category_d = order.getSpecificTax("D");
                const data = await this.pushOrderToSwedenBlackbox(order);
                if (data.error) {
                    throw data;
                }
                this.setDataForPushOrderFromSwedenBlackBox(order, data);
            } catch (data) {
                order.state = "draft";
                throw new SwedenBlackboxError(data?.error ?? data?.status ?? data);
            }
        }
    },
    async pushOrderToSwedenBlackbox(order) {
        const fdm = this.config.iot_fdm_se_id;
        const data = {
            date: new DateTime(order.date_order).toFormat("yyyyMMddHHmm"),
            receipt_id: order.sequence_number.toString(),
            pos_id: this.config.id.toString(),
            organisation_number: (
                this.company.partner_id?.additional_identifiers?.SE_EN || ""
            ).replace(/\D/g, ""),
            receipt_total: order.displayPrice.toFixed(2).toString().replace(".", ","),
            negative_total:
                order.totalDue < 0
                    ? Math.abs(order.totalDue).toFixed(2).toString().replace(".", ",")
                    : "0,00",
            receipt_type: order.receipt_type,
            vat1: order.sweden_blackbox_tax_category_a
                ? "25,00;" + order.sweden_blackbox_tax_category_a.toFixed(2).replace(".", ",")
                : " ",
            vat2: order.sweden_blackbox_tax_category_b
                ? "12,00;" + order.sweden_blackbox_tax_category_b.toFixed(2).replace(".", ",")
                : " ",
            vat3: order.sweden_blackbox_tax_category_c
                ? "6,00;" + order.sweden_blackbox_tax_category_c.toFixed(2).replace(".", ",")
                : " ",
            vat4: order.sweden_blackbox_tax_category_d
                ? "0,00;" + order.sweden_blackbox_tax_category_d.toFixed(2).replace(".", ",")
                : " ",
        };

        return new Promise((resolve, reject) => {
            this.iotHttp.action(
                fdm.iot_id,
                fdm.identifier,
                {
                    action: "registerReceipt",
                    high_level_message: data,
                },
                (data) => {
                    data.status === "success" ? resolve(data.result) : reject(data.result);
                },
                (data) => {
                    if (data.status === "disconnected") {
                        reject(_t("Blackbox is disconnected"));
                    } else {
                        reject(data);
                    }
                }
            );
        });
    },
    setDataForPushOrderFromSwedenBlackBox(order, data) {
        order.sweden_blackbox_signature = data.signature_control;
        order.sweden_blackbox_unit_id = data.unit_id;
    },
    async getOrderSequenceNumber() {
        return await this.data.call("pos.config", "get_order_sequence_number", [this.config.id]);
    },
    async getProfoOrderSequenceNumber() {
        return await this.data.call("pos.config", "get_profo_order_sequence_number", [
            this.config.id,
        ]);
    },
});

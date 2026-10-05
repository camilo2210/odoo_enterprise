import { OrderDetailsDialog } from "@point_of_sale/app/screens/ticket_screen/order_details_dialog/order_details_dialog";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

patch(OrderDetailsDialog.prototype, {
    getOrderFields() {
        const fields = super.getOrderFields();
        const order = this.props.order;

        const origin = fields.find((f) => f.id === "origin");
        if (origin && order.source === "online") {
            Object.assign(origin, {
                value: order.getDeliveryProviderName() || _t("Food Delivery"),
                condition: true,
            });
        }

        ["guests", "served_by"].forEach((id) => {
            const field = fields.find((f) => f.id === id);
            if (field) {
                field.condition = field.condition && !order.delivery_identifier;
            }
        });

        return fields;
    },
});

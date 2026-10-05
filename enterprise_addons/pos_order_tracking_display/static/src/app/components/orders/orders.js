import { Component, useProps, t } from "@odoo/owl";

export class Orders extends Component {
    static template = "pos_order_tracking_display.Orders";
    props = useProps({
        class: t.string().optional(""),
        categoryName: t.string(),
        orders: t.array(),
        ready: t.boolean().optional(false),
    });
}

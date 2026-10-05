import { Component, useProps, t } from "@odoo/owl";
import { usePrepDisplay } from "@pos_enterprise/app/services/preparation_display_service";
import { useService } from "@web/core/utils/hooks";
import { BadgeTag } from "@web/core/tags_list/badge_tag";
import { useDelayedValueChange } from "@pos_enterprise/app/utils/utils";
import { PosPrepLine } from "@pos_enterprise/app/models/pos_prep_line";

export class Orderline extends Component {
    static components = { BadgeTag };
    static template = "pos_enterprise.Orderline";
    props = useProps({
        orderline: t.instanceOf(PosPrepLine),
    });

    setup() {
        this.prepDisplay = usePrepDisplay();
        this.orm = useService("orm");
        this.noteState = useDelayedValueChange(() => this.preparation_line.pos_order_line_id?.note);
    }

    get preparation_line() {
        return this.props.orderline;
    }

    get attributeData() {
        const orderLine = this.preparation_line.pos_order_line_id;
        return Object.values(
            this.preparation_line.attribute_value_ids.reduce((acc, attr) => {
                const customValue =
                    orderLine &&
                    this.prepDisplay.data.models["product.attribute.custom.value"].find(
                        (customValue) =>
                            customValue.pos_order_line_id?.id === orderLine.id &&
                            customValue.custom_product_template_attribute_value_id?.id === attr.id
                    );

                let value = attr.name;
                if (customValue) {
                    value += `: ${customValue.custom_value}`;
                }

                const attributeId = attr.attribute_id?.id;
                if (acc[attributeId]) {
                    acc[attributeId].value += `, ${value}`;
                } else {
                    acc[attributeId] = {
                        id: attr,
                        name: attr.attribute_id?.name,
                        value,
                    };
                }

                return acc;
            }, {})
        );
    }
    get internalNotes() {
        return JSON.parse(this.preparation_line.pos_order_line_id?.note || "[]");
    }
    get customerNotes() {
        return (this.preparation_line.pos_order_line_id?.customer_note || "")
            .split("\n")
            .filter((note) => note);
    }
}

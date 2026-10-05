import { Component, t, useProps } from "@odoo/owl";

export default class OptionLine extends Component {
    static template = "stock_barcode.OptionLine";

    props = useProps({
        line: t.any(),
        additionalClass: t.any().optional(),
        responsible: t.any().optional(),
    });

    get isSelected() {
        if (this.env.model.needPickingType) {
            return this.env.model.selectedPickingTypeId === this.props.line.id;
        } else if (this.env.model.needPickings) {
            return this.env.model.selectedPickings.indexOf(this.props.line.id) !== -1;
        }
        return false;
    }

    select() {
        this.env.model.selectOption(this.props.line.id);
    }
}

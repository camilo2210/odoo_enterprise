import { Component, t, useProps } from "@odoo/owl";
import { registry } from "@web/core/registry";

export const gridRowProps = {
    name: t.string(),
    model: t.object(),
    row: t.object(),
    classNames: t.string().optional(""),
    context: t.object().optional({}),
    style: t.string().optional(""),
    value: t.any().optional(),
};

export class GridRow extends Component {
    static template = "web_grid.GridRow";
    props = useProps(gridRowProps);

    get value() {
        let value =
            this.props.value !== undefined
                ? this.props.value
                : this.props.row.initialRecordValues[this.props.name];
        const fieldInfo = this.props.model.fieldsInfo[this.props.name];
        if (fieldInfo.type === "selection") {
            value = fieldInfo.selection.find(([key]) => key === value)?.[1];
        }
        return value;
    }
}

export const gridRow = {
    component: GridRow,
};

registry.category("grid_components").add("selection", gridRow).add("char", gridRow);

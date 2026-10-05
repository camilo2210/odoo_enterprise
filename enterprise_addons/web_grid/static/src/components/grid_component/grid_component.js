import { Component, computed, t, useProps } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { GridCell } from "../grid_cell";
import { GridRow } from "../grid_row/grid_row";

export class GridComponent extends Component {
    static template = "web_grid.GridComponent";

    props = useProps({
        name: t.any(),
        type: t.any(),
        isMeasure: t.any().optional(),
        component: t.any().optional(),
    });
    // To give to the actual grid component
    gridComponentProps = useProps();

    classNames = computed(() => {
        const classNames = ["o_grid_component", `o_grid_component_${this.props.type}`];
        if (this.gridComponentProps.classNames) {
            classNames.push(this.gridComponentProps.classNames);
        }
        return classNames.join(" ");
    });
    gridComponent = computed(() => {
        if (this.props.component) {
            return this.props.component;
        }
        const definition = registry.category("grid_components").get(this.props.type, {});
        if (definition.component) {
            return definition.component;
        }
        if (this.props.isMeasure) {
            console.warn(`Missing widget: ${this.props.type} for grid component`);
            return GridCell;
        }
        return GridRow;
    });
}

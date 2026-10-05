import { computed, t, useProps } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { GridRow, gridRow } from "../grid_row/grid_row";

export const many2OneGridRowProps = {
    canOpen: t.boolean().optional(true),
};

export class Many2OneGridRow extends GridRow {
    static template = "web_grid.Many2OneGridRow";

    many2OneProps = useProps(many2OneGridRowProps);

    resId = computed(() => this.value && this.value[0]);

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.relation = this.props.model.fieldsInfo[this.props.name].relation;
    }

    get urlRelation() {
        if (!this.relation.includes(".")) {
            return "m-" + this.relation;
        }
        return this.relation;
    }

    get displayName() {
        return this.value && this.value[1].split("\n", 1)[0];
    }

    get extraLines() {
        return this.value
            ? this.value[1]
                  .split("\n")
                  .map((line) => line.trim())
                  .slice(1)
            : [];
    }

    async openAction() {
        const action = await this.orm.call(
            this.relation,
            "get_record_default_action",
            [[this.resId()]],
            {
                context: this.props.context,
            }
        );
        await this.actionService.doAction(action);
    }

    onClick(ev) {
        if (this.many2OneProps.canOpen) {
            ev.stopPropagation();
            this.openAction();
        }
    }
}

export const many2OneGridRow = {
    ...gridRow,
    component: Many2OneGridRow,
};

registry.category("grid_components").add("many2one", many2OneGridRow);

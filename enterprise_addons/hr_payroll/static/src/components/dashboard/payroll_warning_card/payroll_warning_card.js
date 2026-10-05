import { Component, t, useProps } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class PayrollWarningCard extends Component {
    static template = "hr_payroll.PayrollWarningCard";

    props = useProps({
        buttonAction: t.object().optional(),
        buttonName: t.string(),
        colorClass: t.string().optional(),
        count: t.number().optional(),
        description: t.string().optional(),
        id: t.number(),
        isError: t.boolean().optional(),
        isLoading: t.boolean().optional(),
        structureTypeSuffix: t.string().optional(),
        title: t.string(),
    });

    setup() {
        this.action = useService("action");
    }

    doButtonAction() {
        if (!this.props.buttonAction) {
            return;
        }
        this.action.doAction(this.props.buttonAction, {
            additionalContext: { default_structure_type_id: this.props.structureTypeId },
        });
    }
}

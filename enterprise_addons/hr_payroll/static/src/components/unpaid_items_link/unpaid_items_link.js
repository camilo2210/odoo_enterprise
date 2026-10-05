import { Component, useProps } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { useService } from "@web/core/utils/hooks";
import { SelectCreateDialog } from "@web/views/view_dialogs/select_create_dialog";

export class UnpaidItemsLink extends Component {
    static template = "hr_payroll_payment_report_wizard.UnpaidItemsTemp";
    props = useProps(standardWidgetProps);

    setup() {
        this.dialog = useService("dialog");
    }

    async openSelectionList() {
        await this.props.record.save();
        const allowedIds = this.props.record.data.allowed_unpaid_payslip_ids.resIds;
        const list_domain = [['id', 'in', allowedIds]];
        this.dialog.add(SelectCreateDialog, {
            resModel: "hr.payslip", 
            title: "Select Unpaid Items",
            multiSelect: true,
            noCreate: true,
            searchViewId: false, 
            listTemplate: "web.ListRenderer",
            domain: list_domain,
            context: {
                ...this.props.record.context,
                list_view_ref: "hr_payroll.payroll_hr_payslip_list_view_payrun", 
                search_view_ref: "hr_payroll.payroll_hr_payslip_list_view_filter_payrun"
            },
            onSelected: async (resIds) => {
                if (resIds.length > 0) {
                    await this.props.record.update({
                        unpaid_payslips: [[6, 0, resIds]] 
                    });
                    await this.props.record.save();
                }
            },
        });
    }
}

export const unpaidItemsLink = {
    component: UnpaidItemsLink,
    fieldDependencies: [
        { name: "unpaid_payslips_description", type: "char" },
        { name: "allowed_unpaid_payslip_ids", type: "many2many" },
        { name: "unpaid_payslips", type: "many2many" },
    ],
};

registry.category("view_widgets").add("unpaid_items_link", unpaidItemsLink);

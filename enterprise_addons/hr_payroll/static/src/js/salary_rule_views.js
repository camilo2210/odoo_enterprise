/** @odoo-module **/

import { registry } from "@web/core/registry";
import { formView } from "@web/views/form/form_view";
import { FormController } from '@web/views/form/form_controller';
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";
import { _t } from "@web/core/l10n/translation";

export class SalaryRuleFormController extends FormController {
    get deleteConfirmationDialogProps() {
        const base = super.deleteConfirmationDialogProps;
        const record = this.model.root;

        const hasEmployeeProps =
            record.data.condition_select === "property_input" &&
            record.data.input_usage_employee;

        if (!hasEmployeeProps) {
            return base;
        }
        return {
            ...base,
            body: _t(
                "This will delete all the properties on the employees linked to this salary rule and their data. Are you sure you want to continue?"
            ),
        };
    }
}

export class SalaryRuleListController extends ListController {
    async onDeleteSelectedRecords() {
        const props = { ...this.deleteConfirmationDialogProps };
        const selectedResIds = await this.model.root.getResIds(true);
        if (!selectedResIds.length) {
            return;
        }
        const records = await this.orm.read(
            "hr.salary.rule",
            selectedResIds,
            ["condition_select", "input_usage_employee"]
        );
        const hasEmployeeProps = records.some(
            rec =>
                rec.condition_select === "property_input" &&
                rec.input_usage_employee
        );
        if (hasEmployeeProps) {
            props.title = _t("Bye-bye, record!");
            props.body = _t(
                "This will delete all the properties on the employees linked to this salary rule and their data. Are you sure you want to continue?"
            );
        }
        this.deleteRecordsWithConfirmation(props);
    }
}

export const SalaryRuleFormView = {
    ...formView,
    Controller: SalaryRuleFormController,
};

export const SalaryRuleListView = {
    ...listView,
    Controller: SalaryRuleListController,
};

registry.category("views").add("salary_rule_form", SalaryRuleFormView);
registry.category("views").add("salary_rule_list", SalaryRuleListView);

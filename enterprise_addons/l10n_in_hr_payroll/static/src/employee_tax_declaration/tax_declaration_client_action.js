import { _t } from "@web/core/l10n/translation";
import { Component, onWillStart, proxy, useProps } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { usePopover } from "@web/core/popover/popover_hook";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_plugin";
import { HrTaxBreakupPopover } from "@l10n_in_hr_payroll/employee_tax_declaration/hr_tax_breakup_popover";

export class TaxDeclarationClientAction extends Component {
    static template = "l10n_in_hr_payroll.TaxDeclarationClientAction";

    props = useProps(standardActionServiceProps);

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.state = proxy({
            financialYear: "",
        });
        this.hrBreakupPopover = usePopover(HrTaxBreakupPopover, {
            position: "left",
            popoverClass: "bg-view px-3 pt-1",
        });

        onWillStart(async () => {
            await this.loadData();
        });
    }

    get employeeId() {
        return this.props.action.context?.active_id;
    }

    get hasData() {
        return this.declarations.length;
    }

    get lastDeclaration() {
        const declarations = this.declarations;
        return declarations.length ? declarations[declarations.length - 1] : null;
    }

    get overviewCards() {
        const declaration = this.lastDeclaration;
        const values = declaration.formatted_values;
        return [
            {
                key: "total_tds_tobe_paid",
                label: _t("Total Tax to be Paid"),
                value: values.total_tds_tobe_paid,
                valueClass: "",
            },
            {
                key: "already_paid_tds",
                label: _t("Total Tax Paid"),
                value: values.already_paid_tds,
                valueClass: "",
            },
            {
                key: "remaining_tds",
                label: _t("Remaining Tax"),
                value: values.remaining_tds,
                valueClass: "",
            },
            {
                key: "expected_tds",
                label: `${declaration.schedule_label} ${_t("Tax (from")} ${
                    declaration.contract_date_start
                })`,
                value: values.expected_tds,
                valueClass: "text-success",
            },
        ];
    }

    async loadData(financialYear = null) {
        const {
            financial_year: selectedFinancialYear,
            financial_year_options: options,
            declarations,
            contract_count: contractCount,
            version_count: versionCount,
            fy_date_start: fyStartDate,
            fy_date_end: fyEndDate,
        } = await this.orm.call("hr.employee", "l10n_in_get_tax_declaration_view_data", [
            [this.employeeId],
            financialYear,
        ]);
        this.state.financialYear = selectedFinancialYear;
        Object.assign(this, { options, declarations, contractCount, versionCount, fyStartDate, fyEndDate });
    }

    async onFinancialYearChange(ev) {
        await this.loadData(ev.target.value);
    }

    async onShowBreakup(ev, declaration) {
        this.hrBreakupPopover.open(ev.target, {
            taxBreakup: declaration.formatted_values.tax_breakup,
            totalTax: declaration.formatted_values.tax_breakup_total,
        });
    }

    async onPrint() {
        const action = await this.orm.call(
            "hr.employee",
            "l10n_in_get_tax_declaration_report_action",
            [[this.employeeId], this.state.financialYear]
        );
        await this.actionService.doAction(action);
    }
}

registry
    .category("actions")
    .add("l10n_in_hr_payroll.tax_declaration_client_action", TaxDeclarationClientAction);

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { stepUtils } from "@web_tour/tour_utils";
import { markup } from "@odoo/owl";

registry.category("web_tour.tours").add('hr_expense_extract_tour' , {
    steps: () => [
        stepUtils.showAppsMenuItem(), {
        trigger: '.o_app[data-menu-xmlid="hr_expense.menu_hr_expense_root"]',
        content: markup(_t("<b>Wasting time recording your receipts?</b> Let’s try a better way.")),
        tooltipPosition: 'bottom',
        run: "click",
    }, {
        trigger: '.o_nocontent_help a.o_select_sample',
        content: _t("Try the AI with a sample receipt."),
        tooltipPosition: 'bottom',
        run: "click",
    }, {
        trigger: "button[name='action_submit']",
        content: _t("Report this expense to your manager for validation."),
        tooltipPosition: 'bottom',
        run: "click",
    }, {
        trigger: '[data-menu-xmlid="hr_expense.menu_hr_expense_reports"]',
        run: "click",
    }, {
        trigger: 'a[data-menu-xmlid="hr_expense.menu_hr_expense_all_expenses"]',
        content: _t("Your manager will have to approve (or refuse) your expense reports."),
        tooltipPosition: 'bottom',
        run: "click",
    },
]});

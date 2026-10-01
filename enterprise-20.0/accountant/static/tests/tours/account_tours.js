import { patch } from "@web/core/utils/patch";
import { accountTourSteps } from "@account/js/tours/account";
import { stepUtils } from "@web_tour/tour_utils";
import { _t } from "@web/core/l10n/translation";

patch(accountTourSteps, {
    goToAccountMenu(description="Open Accounting Menu") {
        return stepUtils.goToAppSteps('accountant.menu_accounting', description);
    },
    newInvoice() {
        return [
            {
                trigger: ".o_widget_account_onboarding [data-icon='circle'].oi-filled",
            },
            {
                trigger: "button[name=action_create_new]",
                content: _t("Now, we'll create your first invoice (accountant)"),
                run: "click",
            },
        ];
    },
});

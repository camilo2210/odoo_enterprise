import { browser } from "@web/core/browser/browser";
import { patch } from "@web/core/utils/patch";

import { onPatched } from "@odoo/owl";

import { HelpdeskStatusBarDurationField } from "@helpdesk/components/helpdesk_statusbar_duration_field";

patch(HelpdeskStatusBarDurationField.prototype, {
    setup() {
        super.setup();
        onPatched(() => {
            const { record } = this.props;
            if (record.data.use_helpdesk_timesheet && record.data.active) {
                browser.localStorage.setItem(
                    "timesheet.preFilledForm",
                    JSON.stringify({
                        helpdesk_ticket_id: record.resId,
                    })
                );
            }
        });
    },
});

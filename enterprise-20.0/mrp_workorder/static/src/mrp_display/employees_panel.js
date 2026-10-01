import { Component, t, useProps } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { RelativeTime } from "@mail/core/common/relative_time";
import { deserializeDateTime } from "@web/core/l10n/dates";

export class MrpDisplayEmployeesPanel extends Component {
    static template = "mrp_workorder.MrpDisplayEmployeesPanel";
    static components = { RelativeTime };

    props = useProps({
        employees: t.object(),
        setSessionOwner: t.function(),
        popupAddEmployee: t.function(),
    });

    setup() {
        this.ui = useService("ui");
    }

    makeDate(str) {
        const datetime = deserializeDateTime(str);

        // Little hack to never show "now" or "x seconds ago" but always at least 1 min ago.
        return Math.abs(Date.now() - datetime.ts) < 60000
            ? datetime.minus({ seconds: 60 })
            : datetime;
    }
}

import { Component, t, useProps } from "@odoo/owl";
import { formatDate } from "@web/core/l10n/dates";

export class MilestonesPopover extends Component {
    static template = "project_enterprise.MilestonesPopover";

    props = useProps({
        close: t.function(),
        displayMilestoneDates: t.any(),
        displayProjectName: t.any(),
        projects: t.any(),
    });

    getDeadline(milestone) {
        if (!milestone.deadline) {
            return;
        }
        return formatDate(milestone.deadline);
    }
}

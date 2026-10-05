import { Component, useProps, t } from "@odoo/owl";

export class TimesheetKpi extends Component {
    static template = "sale_timesheet_enterprise.TimesheetKpi";
    props = useProps({
        name: t.string(),
        value: t.string(),
        target: t.string().optional(),
        label: t.string(),
        title: t.string(),
        extraClass: t.string().optional(),
        valueExtraClass: t.string().optional(),
        onClick: t.function().optional(() => () => {}),
    });
}

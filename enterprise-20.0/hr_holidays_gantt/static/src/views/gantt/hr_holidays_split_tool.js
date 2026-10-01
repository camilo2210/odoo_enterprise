import { Component, props, types as t } from "@odoo/owl";

export class HrHolidaysSplitTool extends Component {
    static template = "hr_holidays_gantt.HrHolidaysSplitTool";
    props = props({
        position: t.signal(t.string()),
    });
}

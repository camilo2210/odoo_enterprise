import { Component, t, useProps } from "@odoo/owl";

export class PlanningSplitTool extends Component {
    static template = "planning.PlanningSplitTool";

    props = useProps({
        reactive: t.object({
            position: t.string().optional(),
        }),
    });
}

import { Component, useProps, t } from "@odoo/owl";

export class DisplayText extends Component {
    static template = "l10n_it_pos.DisplayText";
    props = useProps({
        operator: t.number().optional(1),
        message: t.string(),
    });
}

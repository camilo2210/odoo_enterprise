import { Component, useProps, t } from "@odoo/owl";

export class DirectIO extends Component {
    static template = "l10n_it_pos.DirectIO";
    props = useProps({
        command: t.string(),
        data: t.string(),
        comment: t.string().optional(""),
    });
}

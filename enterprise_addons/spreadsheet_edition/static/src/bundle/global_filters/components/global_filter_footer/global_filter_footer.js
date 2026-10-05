import { Component, t, useProps } from "@odoo/owl";
import { components } from "@odoo/o-spreadsheet";

const { Section } = components;

export class GlobalFilterFooter extends Component {
    static template = "spreadsheet_edition.GlobalFilterFooter";
    static components = { Section };

    props = useProps({
        onClickCancel: t.function(),
        onClickDelete: t.function().optional(),
        onClickSave: t.function().optional(),
    });
}

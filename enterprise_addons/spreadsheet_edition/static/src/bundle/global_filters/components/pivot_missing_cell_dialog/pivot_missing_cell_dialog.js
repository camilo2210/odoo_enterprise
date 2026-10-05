import { useSubEnv } from "@web/owl2/utils";
import { Dialog } from "@web/core/dialog/dialog";
import { Component, t, useProps } from "@odoo/owl";
import { components } from "@odoo/o-spreadsheet";

const { PivotHTMLRenderer } = components;

export class PivotMissingCellDialog extends Component {
    static template = "spreadsheet_edition.PivotMissingCellDialog";
    static components = { Dialog, PivotHTMLRenderer };

    props = useProps({
        close: t.function(),
        pivotId: t.string(),
        model: t.object(),
        onCellClicked: t.function(),
    });

    setup() {
        useSubEnv({
            model: this.props.model,
        });
    }
}

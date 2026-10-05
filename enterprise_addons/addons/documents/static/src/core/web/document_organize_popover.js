import { Component, markup, t, useProps } from "@odoo/owl";

import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

export class DocumentOrganizePopover extends Component {
    static template = "documents.DocumentOrganizePopover";

    setup() {
        this.store = useService("mail.store");
        this.props = useProps({
            attachment: t.instanceOf(this.store["ir.attachment"]),
            destination: t.string(),
            onOrganizeClick: t.function(),
            close: t.function(),
        });
    }

    get addedToText() {
        return _t("Added to %(destination)s", {
            destination: markup`<strong>${this.props.destination}</strong>`,
        });
    }
}

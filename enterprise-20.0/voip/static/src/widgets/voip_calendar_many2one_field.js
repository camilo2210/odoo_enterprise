import {
    buildM2OFieldDescription,
    many2OneFieldProps,
} from "@web/views/fields/many2one/many2one_field";
import { computeM2OProps, Many2One } from "@web/views/fields/many2one/many2one";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";

import { Component, useProps } from "@odoo/owl";

export class VoipCalendarMany2OneField extends Component {
    static template = "voip.VoipCalendarMany2OneField";
    static components = { Many2One };
    props = useProps({ ...many2OneFieldProps });

    get m2oProps() {
        return computeM2OProps(this.props);
    }
}

registry.category("fields").add("voip_calendar_many2one", {
    ...buildM2OFieldDescription(VoipCalendarMany2OneField),
    displayName: _t("Call Calendar Many2One"),
});

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";

registry.category("builder.form_editor_actions").add("create_ticket", {
    fields: [
        {
            name: "team_id",
            type: "many2one",
            relation: "helpdesk.team",
            string: _t("Helpdesk Team"),
        },
    ],
    successPage: "/your-ticket-has-been-submitted",
});

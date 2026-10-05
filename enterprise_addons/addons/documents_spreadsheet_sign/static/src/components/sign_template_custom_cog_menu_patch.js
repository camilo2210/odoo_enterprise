import { SignTemplateCustomCogMenu } from "@sign/backend_components/cog_menu/sign_template_custom_cog_menu";
import { patch } from "@web/core/utils/patch";
import { onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

patch(SignTemplateCustomCogMenu.prototype, {

    setup() {
        super.setup();

        this.canViewAnswers = false;
        this.action = useService("action");
        onWillStart(async () => {
            const template = this.props.signTemplate;
            const hasSignedRequests = (template.signed_count || 0) > 0;
            this.canViewAnswers = hasSignedRequests;
        });
    },

    async onOpenSpreadsheetClick() {
        return this.action.doActionButton({
            type: "object",
            resModel: "sign.template",
            name: "action_sign_template_open_linked_spreadsheet",
            resIds: [this.props.signTemplate.id],
        });
    },
});

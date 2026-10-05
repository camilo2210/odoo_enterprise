import { Component, onMounted, proxy, t, useProps } from "@odoo/owl";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { useService } from "@web/core/utils/hooks";
import { SignTemplateAccessRights } from "../sign_template/sign_template_access_rights";

export class SignTemplateCustomCogMenu extends Component {
    static template = "sign.SignTemplateCustomCogMenu";
    static components = { Dropdown, DropdownItem };

    props = useProps({
        signTemplate: t.object(),
        hasSignRequests: t.boolean(),
        manageTemplateAccess: t.boolean(),
        onTemplateSaveClick: t.function(),
        documentId: t.number(),
        onEditTemplate: t.function(),
    });

    setup() {
        this.action = useService("action");
        this.notification = useService("notification");
        this.orm = useService("orm");
        this.dialogService = useService("dialog");
        this.state = proxy({
            properties: false,
        });

        onMounted(async () => {
            await this.setTemplateDisplayName();
        });
    }

    async onTemplatePropertiesClick() {
        const action = await this.action.loadAction("sign.action_sign_template_cog_menu");
        action.res_id = this.props.signTemplate.id;
        this.action.doAction(action, {
            onClose: async () => {
                await this.setTemplateDisplayName();
            },
        });
    }

    async setTemplateDisplayName() {
        if (!this.props.signTemplate) {
            return;
        }

        // Fetch updated name
        const template = await this.orm.read(
            "sign.template",
            [this.props.signTemplate.id],
            ["name"]
        );
        this.env.config.setDisplayName(template[0].name);
    }

    get showEditButton() {
        return this.props.hasSignRequests;
    }

    onAccessRightsClick() {
        this.dialogService.add(SignTemplateAccessRights, {
            signTemplate: this.props.signTemplate,
            hasSignRequests: this.props.hasSignRequests,
        });
    }

    onPreviewClick() {
        this.action.doActionButton({
            type: "object",
            resModel: "sign.template",
            name: "action_template_preview",
            resIds: [this.props.signTemplate.id],
            args: JSON.stringify([this.props.documentId]),
        });
    }
}

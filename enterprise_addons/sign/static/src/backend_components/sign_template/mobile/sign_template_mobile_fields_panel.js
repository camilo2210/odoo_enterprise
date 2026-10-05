import { Component, proxy, t, useProps } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import {
    FIELD_TYPE_ICONS,
    addCustomFieldType,
} from "@sign/backend_components/sign_template/sign_template_sidebar_role_items";

export class SignTemplateMobileFieldsPanel extends Component {
    static template = "sign.SignTemplateMobileFieldsPanel";

    props = useProps({
        signItemTypes: t.array(),
        signer: t.object().optional(),
        documentName: t.string(),
        hasSignRequests: t.boolean(),
        iframe: t.object().optional(),
        fetchSignItemTypes: t.function(),
    });

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.icon_type = FIELD_TYPE_ICONS;
        this.state = proxy({
            signItemTypes: this.props.signItemTypes,
            isAdmin: user.isAdmin,
        });
    }

    onAddCustomField() {
        return addCustomFieldType({
            orm: this.orm,
            action: this.action,
            fetchSignItemTypes: () => this.props.fetchSignItemTypes(),
            iframe: this.props.iframe,
            onFetched: (signItemTypes) => {
                this.state.signItemTypes = signItemTypes;
            },
        });
    }
}

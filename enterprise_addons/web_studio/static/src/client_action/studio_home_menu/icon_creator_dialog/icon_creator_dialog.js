import { Dialog } from "@web/core/dialog/dialog";
import { rpc } from "@web/core/network/rpc";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { IconCreator } from "@web_studio/client_action/icon_creator/icon_creator";

import { Component, proxy, t, useProps } from "@odoo/owl";

export class IconCreatorDialog extends Component {
    static components = { Dialog, IconCreator };
    static template = "web_studio.IconCreatorDialog";

    props = useProps({
        editedAppData: t.object(),
        appId: t.number(),
        close: t.function(),
    });

    setup() {
        this.menus = useService("menu");
        this.initialAppData = { ...this.props.editedAppData };
        this.editedAppData = proxy(this.props.editedAppData);
    }

    /**
     * @param {Object} icon
     */
    onIconChanged(icon) {
        for (const key in this.editedAppData) {
            delete this.editedAppData[key];
        }
        for (const key in icon) {
            this.editedAppData[key] = icon[key];
        }
    }

    async saveIcon() {
        const { type } = this.initialAppData;
        const appId = this.props.appId;
        let iconValue;
        if (this.editedAppData.type !== type) {
            // different type
            if (this.editedAppData.type === "base64") {
                iconValue = this.editedAppData.uploaded_attachment_id;
            } else {
                const { icon, color, backgroundColor } = this.editedAppData;
                iconValue = [icon, color, backgroundColor];
            }
        } else if (this.editedAppData.type === "custom_icon") {
            // custom icon changed
            const { icon, color, backgroundColor } = this.editedAppData;
            if (
                this.initialAppData.icon !== icon ||
                this.initialAppData.color !== color ||
                this.initialAppData.backgroundColor !== backgroundColor
            ) {
                iconValue = [icon, color, backgroundColor];
            }
        } else if (this.editedAppData.uploaded_attachment_id) {
            // new attachment
            iconValue = this.editedAppData.uploaded_attachment_id;
        }

        if (iconValue) {
            await rpc("/web_studio/edit_menu_icon", {
                context: user.context,
                icon: iconValue,
                menu_id: appId,
            });
            await this.menus.reload();
        }
        this.props.close();
    }
}

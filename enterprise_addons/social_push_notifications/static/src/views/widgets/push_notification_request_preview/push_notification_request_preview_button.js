import { Component, proxy, useProps } from "@odoo/owl";
import { PushNotificationRequest } from "@social_push_notifications/components/push_notification_request/push_notification_request";
import { registry } from "@web/core/registry";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { dataUrlToBlob } from "@mail/core/common/attachment_uploader_hook";

const mainComponents = registry.category("main_components");

class PushNotificationRequestPreviewButton extends Component {
    static template = "social_push_notifications.PushNotificationRequestPreviewButton";

    props = useProps(standardWidgetProps);

    setup() {
        this.config = proxy({});
    }

    onPreviewBtnClick() {
        const { data } = this.props.record;
        this.config.title = data.notification_request_title;
        this.config.body = data.notification_request_body;
        if (this.config.icon) {
            URL.revokeObjectURL(this.config.icon);
        }
        if (data.notification_request_icon) {
            const blob = dataUrlToBlob(data.notification_request_icon, "image/*");
            this.config.icon = URL.createObjectURL(blob);
        } else {
            this.config.icon = "";
        }

        const key = "social_push_notifications.push_notification_request";
        if (mainComponents.get(key, false)) {
            mainComponents.remove(key);
        }
        const closePopup = () => {
            mainComponents.remove(key);
            if (this.config.icon) {
                URL.revokeObjectURL(this.config.icon);
            }
        };
        mainComponents.add(key, {
            Component: PushNotificationRequest,
            props: {
                config: this.config,
                onAllowPushNotifications: closePopup,
                onDenyPushNotifications: closePopup,
                close: closePopup,
            },
        });
    }
}

export const pushNotificationRequestPreviewButton = {
    component: PushNotificationRequestPreviewButton,
};

registry.category("view_widgets").add(
    "push_notification_request_preview_button",
    pushNotificationRequestPreviewButton
);

import { Component, onMounted, onWillUnmount, t, useProps } from "@odoo/owl";

export class PushNotificationRequest extends Component {
    static template = "social_push_notifications.PushNotificationRequest";

    props = useProps({
        config: t.object(),
        onAllowPushNotifications: t.function(),
        onDenyPushNotifications: t.function(),
        close: t.function(),
    });

    setup() {
        /** @param {Event} event */
        const onClosePopup = event => {
            if (!event.target.closest(".o_social_push_notification_request")) {
                this.props.close();
            }
        };
        onMounted(() => {
            document.body.addEventListener("click", onClosePopup, { capture: true });
        });
        onWillUnmount(() => {
            document.body.removeEventListener("click", onClosePopup, { capture: true });
        });
    }
}

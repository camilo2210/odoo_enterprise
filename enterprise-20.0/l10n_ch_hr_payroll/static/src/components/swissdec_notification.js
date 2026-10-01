/** @odoo-module **/
import { Component, t, useProps } from "@odoo/owl";

export class SwissdecNotification extends Component {
    static template = "swissdec_notification_template";
    props = useProps({
        type: t.string(),
        notifications: t.array(),
    });
}

export default SwissdecNotification;

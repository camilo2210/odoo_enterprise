import { registry } from "@web/core/registry";
import { Component, onWillStart, onWillUnmount, t, useProps } from "@odoo/owl";
import { useInactivity } from "../use_inactivity";

export class RegisterPage extends Component {
    static template = "frontdesk.RegisterPage";

    props = useProps({
        createVisitor: t.function(),
        hostData: t.any().optional(),
        isMobile: t.boolean(),
        onClose: t.function(),
        showScreen: t.function(),
        theme: t.string(),
    });

    setup() {
        if (!this.props.isMobile) {
            useInactivity(() => this.props.onClose(), 15000);
        }

        onWillStart(async () => {
            const visitorCreated = sessionStorage.getItem("visitorCreated");
            if (!visitorCreated) {
                await this.props.createVisitor();
                if (this.props.isMobile) {
                    // Set the flag in sessionStorage
                    sessionStorage.setItem("visitorCreated", "true");
                }
            }
        });

        onWillUnmount(() => {
            if (this.props.isMobile) {
                // Clear the visitorCreated flag
                sessionStorage.removeItem("visitorCreated");
            }
        });
    }
}

registry.category("frontdesk_screens").add("RegisterPage", RegisterPage);

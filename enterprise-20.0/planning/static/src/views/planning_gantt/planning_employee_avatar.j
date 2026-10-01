import { Avatar } from "@mail/views/web/fields/avatar/avatar";

import { useProps, signal, t } from "@odoo/owl";
import { setupDisplayName } from "../planning_hooks";

export class PlanningEmployeeAvatar extends Avatar {
    static template = "planning.PlanningEmployeeAvatar";

    setup() {
        super.setup();
        this.planningProps = useProps({
            isResourceMaterial: t.boolean().optional(),
            resourceColor: t.number().optional(),
            showPopover: t.boolean().optional(),
        });
        this.displayNameRef = signal.ref();
        setupDisplayName(this.displayNameRef);
    }

    openCard(ev) {
        if (this.uiService.isSmall || !this.planningProps.showPopover) {
            return;
        }
        const target = ev.currentTarget;
        if (!this.avatarCard.isOpen) {
            this.avatarCard.open(target, {
                id: this.props.resId,
                model: this.props.resModel,
            });
        }
    }
}

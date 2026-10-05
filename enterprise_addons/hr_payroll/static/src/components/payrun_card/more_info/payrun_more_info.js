import { Component, computed, onWillStart, useProps, proxy, t } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { usePopover } from "@web/core/popover/popover_hook";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { Field } from "@web/views/fields/field";

export class MoreInfo extends Component {
    static template = "hr_payroll.MoreInfo";
    props = useProps({
        slots: t.object().optional({}),
    });

    allowedSlots = computed(() =>
        this.computeMoreInfo(this.props.slots, this.cacheAllowedGroups)
    );

    setup() {
        this.moreInfoCard = usePopover(MoreInfoCardPopover);
        this.cacheAllowedGroups = proxy([]);
        onWillStart(async () => {
            if (Object.values(this.props.slots).some((slot) => slot.group)) {
                await this.computeAllowedGroups(this.props.slots);
            }
        });
    }

    async computeAllowedGroups(slots) {
        for (const [, slot] of Object.entries(slots)) {
            if (!slot.group || this.cacheAllowedGroups.includes(slot.group)) {
                continue;
            }
            if (await user.hasGroup(slot.group)) {
                this.cacheAllowedGroups.push(slot.group);
            }
        }
    }

    computeMoreInfo(slots, cacheAllowedGroups = []) {
        const result = Object.entries(slots).map(([slotName, slot]) => {
            if (!slot.isVisible) {
                return null;
            }
            return !slot.group || cacheAllowedGroups.includes(slot.group) ? [slotName, slot] : null;
        });
        return Object.fromEntries(result.filter(Boolean));
    }

    onClickMoreInfo(ev) {
        if (!this.moreInfoCard.isOpen) {
            this.moreInfoCard.open(ev.currentTarget, {
                slots: this.allowedSlots(),
            });
        }
    }

    async hasGroup(group) {
        return group ? user.hasGroup(group) : true;
    }
}

export class MoreInfoCardPopover extends Component {
    static template = "hr_payroll.MoreInfoCardPopover";
    static subTemplates = {
        popover: "hr_payroll.MoreInfoCardPopover.popover",
        body: "hr_payroll.MoreInfoCardPopover.body",
    };
    props = useProps({
        slots: t.object().optional(),
        close: t.function().optional(),
    });

    static components = {
        Field,
        Dialog,
    };

    setup() {
        this.uiService = useService("ui");
    }
}

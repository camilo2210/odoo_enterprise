import { onWillStart, Component, useProps, t, computed, proxy } from "@odoo/owl";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { user } from "@web/core/user";

export class PayRunButtonBox extends Component {
    static template = "hr_payroll.PayRunButtonBox";
    static components = {
        Dropdown,
        DropdownItem,
    };
    props = useProps({
        slots: t.object().optional({}),
        class: t.string().optional(""),
    });

    get isSelectionActive() {
        const selection = this.env.model?.root?.selection;
        return selection && selection.length > 0;
    }

    buttonVisibility = computed(() =>
        this.computeAllowedButtons(this.props.slots, this.cacheAllowedGroups)
    );

    setup() {
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

    computeAllowedButtons(slots, cacheAllowedGroups = []) {
        const allVisibleButtons = Object.entries(slots).map(([slotName, slot]) => {
            if (!slot.isVisible) {
                return null;
            }
            return !slot.group || cacheAllowedGroups.includes(slot.group) ? [slotName, slot] : null;
        });

        const [priorityVisibleActionButtons, normalVisibleActionButtons, smartButtonsVisible] =
            allVisibleButtons.filter(Boolean).reduce(
                ([priority, normal, smart], [slotName, slot]) => {
                    if (slot.isPriority) {
                        priority.push(slotName);
                    } else if (slot.isSmartButton) {
                        smart.push(slotName);
                    } else {
                        normal.push(slotName);
                    }
                    return [priority, normal, smart];
                },
                [[], [], []]
            );

        const allVisibleActionButtons = [
            ...priorityVisibleActionButtons,
            ...normalVisibleActionButtons,
        ];
        const inlineCount = priorityVisibleActionButtons.length ? 2 : 1;
        return {
            allSmartButtons: smartButtonsVisible,
            inlineActionButtons: allVisibleActionButtons.slice(0, inlineCount),
            menuActionButtons: allVisibleActionButtons.slice(inlineCount),
        };
    }
}

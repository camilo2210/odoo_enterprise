import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { PlanningSlotSelectionPopup } from "@pos_sale_planning/app/components/planning_slot_selection_popup/planning_slot_selection_popup";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";

const { DateTime } = luxon;

patch(PlanningSlotSelectionPopup, {
    components: { ...PlanningSlotSelectionPopup.components, Dropdown, DropdownItem },
});
patch(PlanningSlotSelectionPopup.prototype, {
    setup() {
        super.setup();
        this.state.showFilterOptions = false;
        this.state.selectedFilter = "all";
    },
    get filterOptions() {
        return {
            all: { text: _t("All") },
            pickup: { text: _t("Not checked") },
            return: { text: _t("Checked in") },
            returned: { text: _t("Checked out") },
        };
    },
    get filterOptionsList() {
        return Object.keys(this.filterOptions);
    },
    _onSelectFilter(key) {
        this.state.selectedFilter = key;
        this.state.showFilterOptions = false;
    },
    get slotsToDisplay() {
        const slots = super.slotsToDisplay;
        if (this.state.selectedFilter === "all") {
            return slots;
        }
        return slots.filter((slot) => slot.rental_status === this.state.selectedFilter);
    },
    getRentalStatus(slot) {
        const statusMapping = {
            pickup: "Not checked",
            return: "Checked in",
            returned: "Checked out",
        };
        return statusMapping[slot.rental_status] || _t("N/A");
    },

    getRentalStatusClass(slot) {
        const statusMapping = {
            pickup: "text-bg-info",
            return: "text-bg-success",
            returned: "text-bg-error",
        };
        return statusMapping[slot.rental_status] || "text-bg-secondary";
    },
    async getNewSlots() {
        await super.getNewSlots();
        const now = DateTime.now();
        this.state.slotsToDisplay = this.state.slotsToDisplay.sort((a, b) => {
            if (a.rental_status === b.rental_status) {
                if (a.rental_status === "pickup") {
                    return Math.abs(a.start_datetime - now) - Math.abs(b.start_datetime - now);
                }
                return Math.abs(a.end_datetime - now) - Math.abs(b.end_datetime - now);
            }
            if (a.rental_status === "return") {
                return -1;
            } else if (b.rental_status === "return") {
                return 1;
            }
            return Math.abs(a.start_datetime - now) - Math.abs(b.start_datetime - now);
        });
    },
    getFetchOpts() {
        return {
            rental_status: this.state.selectedFilter === "all" ? null : this.state.selectedFilter,
        };
    },
});

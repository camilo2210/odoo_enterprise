import { Dialog } from "@web/core/dialog/dialog";
import { Input } from "@point_of_sale/app/components/inputs/input/input";
import { Component, proxy, signal, useProps, t, untrack } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { normalize } from "@web/core/l10n/utils";
import { debounce } from "@web/core/utils/timing";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";
import { useHotkey } from "@web/core/hotkeys/hotkey_hook";
import { useLayoutEffect } from "@web/owl2/utils";

export class PlanningSlotSelectionPopup extends Component {
    static components = { Dialog, Input };
    static template = "pos_sale_planning.PlanningSlotSelectionPopup";
    props = useProps({
        paymentMethodId: t.number(),
        orderUuid: t.string(),
        availableSlots: t.array(),
        getPayload: t.function(),
        close: t.function(),
    });

    setup() {
        this.pos = usePos();
        this.ui = useService("ui");
        this.modalRef = signal.ref();
        this.state = proxy({
            query: "",
            loading: false,
            offsetBySearch: {
                "": this.props.availableSlots.length,
            },
            slotsToDisplay: this.props.availableSlots,
        });
        this.loadedSlotIds = new Set(this.props.availableSlots.map((slot) => slot.id));

        this.onScroll = debounce(this.onScroll.bind(this), 200);

        useLayoutEffect(
            () => {
                if (this.state.loading || !this.modalRef()) {
                    return;
                } else if (!this.modalContent) {
                    this.modalContent = this.modalRef().querySelector(".modal-body");
                }

                const scrollMethod = this.onScroll.bind(this);
                this.modalContent.addEventListener("scroll", scrollMethod);
                return () => {
                    this.modalContent.removeEventListener("scroll", scrollMethod);
                };
            },
            () => [untrack(this.modalRef)]
        );

        useHotkey("enter", () => this.getNewSlots(), { bypassEditableProtection: true });
    }

    onScroll() {
        if (this.state.loading || !this.modalContent) {
            return;
        }
        const height = this.modalContent.offsetHeight;
        const scrollTop = this.modalContent.scrollTop;
        const scrollHeight = this.modalContent.scrollHeight;

        if (scrollTop + height >= scrollHeight * 0.8) {
            this.getNewSlots();
        }
    }

    get slotsToDisplay() {
        if (!this.state.query) {
            return this.state.slotsToDisplay;
        }
        const searchWord = normalize(this.state.query.trim() ?? "");
        const nameMatches = [];
        const slotMatches = [];

        for (const slot of this.state.slotsToDisplay) {
            const resourceName = slot.resource_ids[0].name.toLowerCase();
            const slotName = slot.display_name.toLowerCase();
            const matchesResourceName = resourceName.includes(searchWord);
            const matchesSlotName = slotName.includes(searchWord);

            if (matchesResourceName) {
                nameMatches.push(slot);
            } else if (matchesSlotName) {
                slotMatches.push(slot);
            }
        }

        nameMatches.sort((a, b) => a.resource_ids[0].name.length - b.resource_ids[0].name.length);
        slotMatches.sort((a, b) => a.display_name.length - b.display_name.length);

        return [...nameMatches, ...slotMatches];
    }

    async getNewSlots() {
        try {
            this.state.loading = true;
            const order = this.pos.models["pos.order"].getBy("uuid", this.props.orderUuid);
            const paymentMethod = this.pos.models["pos.payment.method"].get(
                this.props.paymentMethodId
            );
            const offset = this.state.offsetBySearch[this.state.query] || 0;
            const slots = await this.pos.fetchSlots(
                paymentMethod,
                order,
                this.state.query,
                offset,
                this.getFetchOpts()
            );
            const newSlots = slots.filter((slot) => !this.loadedSlotIds.has(slot.id));
            newSlots.forEach((slot) => this.loadedSlotIds.add(slot.id));
            this.state.slotsToDisplay = [...this.state.slotsToDisplay, ...newSlots].sort(
                (a, b) => b.end_datetime - a.end_datetime
            );
            this.state.offsetBySearch[this.state.query] = offset + slots.length;
        } finally {
            this.state.loading = false;
        }
    }

    getFetchOpts() {
        return {};
    }

    confirm(resource) {
        this.props.getPayload(resource);
        this.props.close();
    }
}

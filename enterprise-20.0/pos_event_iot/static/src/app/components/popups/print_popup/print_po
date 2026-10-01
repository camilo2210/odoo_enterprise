import { PrintPopup } from "@point_of_sale/app/components/popups/print_popup/print_popup";
import { patch } from "@web/core/utils/patch";

patch(PrintPopup.prototype, {
    async printEventBadge() {
        const registrations = this.order.eventRegistrations;

        const badgePrinterRegistrations = registrations.filter(
            (reg) => reg.event_id.badge_format === "96x82"
        );
        const nonBadgePrinterRegistrations = registrations.filter(
            (reg) => reg.event_id.badge_format !== "96x82"
        );

        if (nonBadgePrinterRegistrations.length > 0) {
            await this.report.doAction(
                "event.action_report_event_registration_badge",
                nonBadgePrinterRegistrations.map((reg) => reg.id)
            );
        }
        if (badgePrinterRegistrations.length > 0) {
            await this.report.doAction(
                "event_iot.action_report_event_registration_badge_96x82",
                badgePrinterRegistrations.map((reg) => reg.id)
            );
        }

        // Update the status to "attended" if we print the attendee badge
        if (registrations.length > 0) {
            const registrationIds = registrations.map((registration) => registration.id);
            await this.pos.data.ormWrite("event.registration", registrationIds, { state: "done" });
        }
    },
});

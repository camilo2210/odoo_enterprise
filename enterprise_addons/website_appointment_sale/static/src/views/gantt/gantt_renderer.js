import { patch } from "@web/core/utils/patch";
import { AppointmentBookingGanttRenderer } from "@appointment/views/gantt/gantt_renderer";


patch(AppointmentBookingGanttRenderer.prototype, {
    /**
     * @override
     * Add an orange upper left triangle on gantt pills when the meeting
     * is not linked to any sale order while linked on an appointment type
     * with a payment step. The hatched effect of decoration info will not
     * be lost.
     */
    enrichPill(pill) {
        const { record } = pill;
        const enrichedPill = super.enrichPill(pill);
        if (record.show_create_so_btn) {
            enrichedPill.className += ` decoration-warning`;
        }
        return enrichedPill;
    }
});

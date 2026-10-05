import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { FrequencyViewer } from "@timesheet_grid/components/aw_timesheet/frequency_viewer/frequency_viewer";

patch(FrequencyViewer.prototype, {
    get fields() {
        return {
            ...super.fields,
            ticket: { type: "char", name: "ticket", string: _t("Ticket") },
        };
    },

    get idToModel() {
        return {
            ...super.idToModel,
            heldepsk_ticket_id: "helpdesk.ticket",
        };
    },

    getRecordData(parsed, names) {
        return {
            ...super.getRecordData(parsed, names),
            ticket: names.heldepsk_ticket_id?.[parsed.heldepsk_ticket_id],
        };
    },
});

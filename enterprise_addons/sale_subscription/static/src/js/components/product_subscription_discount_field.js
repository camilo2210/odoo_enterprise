import { patch } from "@web/core/utils/patch";
import { SectionAndNoteListRenderer } from "@account/components/section_and_note_fields_backend/section_and_note_fields_backend";

patch(SectionAndNoteListRenderer.prototype, {
    isSectionOrNote(record = null) {
        record = record || this.record;
        const data = super.isSectionOrNote(record);
        return data || record.data.display_type === "subscription_discount";
    },
});

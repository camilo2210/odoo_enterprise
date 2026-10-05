import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { ProductLabelSectionAndNoteListRender } from '@account/components/product_label_section_and_note_o2m/product_label_section_and_note_field_o2m';
import { M2OCellWithExtraFields } from '@account/components/m2o_cell_with_extra_fields/m2o_cell_with_extra_fields';
import { DateTimeField } from "@web/views/fields/datetime/datetime_field";


patch(ProductLabelSectionAndNoteListRender.prototype, {
    getActiveColumns() {
        let activeColumns = super.getActiveColumns();

        const isDeferredDateColumnActive = activeColumns.some((col) => col.name === "deferred_start_date");
        this.props.list.records.forEach((record) => {
            // Assign based on the global column presence
            record.showDeferredDate = isDeferredDateColumnActive || record.data.is_deferred_account;
        });

        // Always remove the deferred start date and deferred end date columns from active columns & show them under account
        return activeColumns.filter((col) => !["deferred_start_date", "deferred_end_date"].includes(col.name));
    }
});

Object.assign(M2OCellWithExtraFields.components, {
    DateTimeField
});

patch(M2OCellWithExtraFields.prototype, {
    get extraDeferredDateInfo() {
        return {
            props:{
                // Standard Field Props
                name: "deferred_start_date",
                record: this.props.record,
                readonly: this.isReadonlyList || this.props.record.data.has_deferred_moves,
                // DateTime props
                placeholder: _t("Deferred Date"),
                endDateField: "deferred_end_date",
                alwaysRange: true,
            },
            decorationWarning: this.props.record.data.has_abnormal_deferred_dates,
            invisible: this.props.name !== 'account_id' || !this.props.record.showDeferredDate,
            required: this.props.record.data.is_deferred_account,
        };
    }
});

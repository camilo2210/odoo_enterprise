import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { computeM2OProps } from "@web/views/fields/many2one/many2one";
import { ProductLabelSectionAndNoteListRender } from '@account/components/product_label_section_and_note_o2m/product_label_section_and_note_field_o2m';
import { M2OCellWithExtraFields } from '@account/components/m2o_cell_with_extra_fields/m2o_cell_with_extra_fields';

patch(ProductLabelSectionAndNoteListRender.prototype, {
    getActiveColumns() {
        let activeColumns = super.getActiveColumns();
        const isSelected = activeColumns.some((col) => col.name === "vehicle_id");

        // If vehicle_id is required and empty then we always show it for that record even if unselected
        this.props.list.records.forEach((record) => (record.showVehicle = isSelected || record.data.need_vehicle));

        // Always remove the vehicle column from active columns & show under account
        activeColumns = activeColumns.filter((col) => col.name !== "vehicle_id");
        return activeColumns;
    }
});

patch(M2OCellWithExtraFields.prototype, {
    get extraVehicleProps() {
        const isDraft = this.props.record.evalContext.parent.state === "draft";
        const m2oProps = computeM2OProps({
            ...this.props,
            name: "vehicle_id",
            placeholder: _t("Vehicle"),
            string: _t("Vehicle"),
            canOpen: !isDraft,
            canCreateEdit: true,
            context: {
                form_view_ref: "account_asset_fleet.fleet_vehicle_view_form",
            },
            domain: undefined,
        });
        return {
            props: {
                ...m2oProps,
                readonly: this.isReadonlyList,
            },
            invisible: this.props.name !== 'account_id' || !this.props.record.showVehicle,
            required: this.props.record.data.need_vehicle,
        };
    }
});

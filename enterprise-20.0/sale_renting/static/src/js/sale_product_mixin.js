import { SaleOrderLineProductField } from "@sale/js/sale_product_field/sale_product_field";
import { SaleLabelTextField } from "@sale/js/sale_label_text/sale_label_text";
import { serializeDateTime } from "@web/core/l10n/dates";
import { patch } from "@web/core/utils/patch";

// !Keep these patches separate: patch() mutates the extension object to wire `super`,
// !so sharing or spreading one object across both prototypes breaks the `super` chain.

patch(SaleLabelTextField.prototype, {
    _getAdditionalRpcParams() {
        const params = super._getAdditionalRpcParams();
        const { rental_start_date, rental_return_date } = this.props.record.model.root.data;
        if (rental_start_date && rental_return_date) {
            params.start_date = serializeDateTime(rental_start_date);
            params.end_date = serializeDateTime(rental_return_date);
        }
        return params;
    },

    _getAdditionalDialogProps() {
        const props = super._getAdditionalDialogProps();
        const { rental_start_date, rental_return_date } = this.props.record.model.root.data;
        if (rental_start_date && rental_return_date) {
            props.start_date = serializeDateTime(rental_start_date);
            props.end_date = serializeDateTime(rental_return_date);
        }
        return props;
    },

    get m2xAutocompleteProps() {
        const props = super.m2xAutocompleteProps;
        return {
            ...props,
            context: {
                ...props.context,
                show_rental_tag: props.context.autocomplete_show_rental_tag,
            },
        };
    },
});

patch(SaleOrderLineProductField.prototype, {
    _getAdditionalRpcParams() {
        const params = super._getAdditionalRpcParams();
        const { rental_start_date, rental_return_date } = this.props.record.model.root.data;
        if (rental_start_date && rental_return_date) {
            params.start_date = serializeDateTime(rental_start_date);
            params.end_date = serializeDateTime(rental_return_date);
        }
        return params;
    },

    _getAdditionalDialogProps() {
        const props = super._getAdditionalDialogProps();
        const { rental_start_date, rental_return_date } = this.props.record.model.root.data;
        if (rental_start_date && rental_return_date) {
            props.start_date = serializeDateTime(rental_start_date);
            props.end_date = serializeDateTime(rental_return_date);
        }
        return props;
    },

    get m2oProps() {
        const props = super.m2oProps;
        return {
            ...props,
            context: {
                ...props.context,
                show_rental_tag: props.context.autocomplete_show_rental_tag,
            },
        };
    },
});

import { t } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";

import {
    LocationSelectorDialog,
    locationSelectorDialogProps,
} from '@website_sale_stock/js/location_selector/location_selector_dialog/location_selector_dialog';

Object.assign(locationSelectorDialogProps, {
    isRental: t.boolean().optional(),
    fromDate: t.string().optional(),
    toDate: t.string().optional(),
});

patch(LocationSelectorDialog.prototype, {
    _getLocationsParams() {
        const params = super._getLocationsParams(...arguments);
        if (this.props.isRental) {
            params.start_date = this.props.fromDate;
            params.end_date = this.props.toDate;
        }
        return params;
    },
});

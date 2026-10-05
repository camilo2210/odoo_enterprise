import { patch } from "@web/core/utils/patch";

import { ClickAndCollectAvailability } from "@website_sale_collect/js/click_and_collect_availability/click_and_collect_availability";

patch(ClickAndCollectAvailability.prototype, {
    _updateStateWithCombinationInfo(combinationInfo) {
        super._updateStateWithCombinationInfo(combinationInfo);
        this.state.isRental = combinationInfo.is_rental;
        this.state.fromDate = combinationInfo.default_start_date;
        this.state.toDate = combinationInfo.default_end_date;
    },
    _getLocationSelectorDialogProps() {
        const props = super._getLocationSelectorDialogProps();
        return {
            ...props,
            isRental: this.state.isRental,
            fromDate: this.state.fromDate,
            toDate: this.state.toDate,
        };
    },
    async _saveSelectedLocation(location) {
        await super._saveSelectedLocation(location);
        const daterangePickers = document.querySelectorAll(".o_website_sale_daterange_picker");
        daterangePickers.forEach((el) =>
            el.dispatchEvent(new CustomEvent("reload_product_availabilities"))
        );
    },
});

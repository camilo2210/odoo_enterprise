import { Interaction } from '@web/public/interaction';
import { registry } from '@web/core/registry';
import { serializeDateTime } from '@web/core/l10n/dates';
import { redirect } from '@web/core/utils/urls';
import daterangePickerUtils from '@website_sale_renting/js/daterange_picker_utils';

export class RentalSearchSnippet extends Interaction {
    static selector = '.s_rental_search';
    dynamicContent = {
        '.s_rental_search_btn': { 't-on-click': this.onClickRentalSearchButton },
        '.o_website_sale_daterange_picker': {
            't-on-daterange_validity_changed': this.toggleSearchButton,
        },
    };

    toggleSearchButton(ev) {
        ev.currentTarget.querySelector('.s_rental_search_btn').disabled = !ev.detail.isValid;
    }

    onClickRentalSearchButton() {
        const daterangePicker = this.el.querySelector('.o_website_sale_daterange_picker');
        const { startDate, endDate } = daterangePickerUtils.getRentalDates(daterangePicker);
        this.searchRentals({ detail: { startDate: startDate, endDate: endDate }});
    }

    /**
     * This function is triggered when the user clicks on the rental search button.
     *
     * @param {CustomEvent} event
     */
    searchRentals(event) {
        const { startDate, endDate } = event.detail;
        const searchParams = new URLSearchParams();
        if (startDate && endDate) {
            searchParams.append('start_date', serializeDateTime(startDate));
            searchParams.append('end_date', serializeDateTime(endDate));
        }
        const productAttributeId = this.el.querySelector('.product_attribute_search_rental_name').id;

        const productAttributeValueId = this.el.querySelector('.s_rental_search_select').value;
        if (productAttributeValueId) {
            // TODO(loti): ideally, we should use slugs instead of ids, but the data is populated in
            // the frontend, so we don't have the info.
            searchParams.append(productAttributeId, productAttributeValueId);
        }
        redirect(`/shop?${searchParams.toString()}`);
    }
}

registry
    .category('public.interactions')
    .add('website_sale_renting.rental_search_snippet', RentalSearchSnippet);

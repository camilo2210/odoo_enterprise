import { serializeDateTime } from '@web/core/l10n/dates';
import { patch } from '@web/core/utils/patch';
import { redirect } from '@web/core/utils/urls';
import { patchDynamicContent } from '@web/public/utils';
import { ShopPage } from '@website_sale/interactions/shop_page';

patch(ShopPage.prototype, {
    setup() {
        super.setup();
        patchDynamicContent(this.dynamicContent, {
            '.o_website_sale_daterange_picker': {
                't-on-daterange_picker_applied': this.onDaterangePickerApplied.bind(this),
            },
            '.clear-daterange': { 't-on-click': this.onDatePickerClear.bind(this) },
        });
    },

    /**
     * @param {CustomEvent} event
     */
    onDaterangePickerApplied(event) {
        const { startDate, endDate } = event.detail;
        const searchParams = new URLSearchParams(window.location.search);
        if (startDate && endDate) {
            searchParams.set('start_date', serializeDateTime(startDate));
            searchParams.set('end_date', serializeDateTime(endDate));
        }
        redirect(`/shop?${searchParams.toString()}`);
    },

    onDatePickerClear() {
        const searchParams = new URLSearchParams(window.location.search);
        searchParams.delete('start_date');
        searchParams.delete('end_date');
        window.location.search = searchParams.toString();
    },
});

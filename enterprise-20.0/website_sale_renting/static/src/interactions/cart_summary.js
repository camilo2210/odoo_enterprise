import { markup } from '@odoo/owl';
import { Interaction } from '@web/public/interaction';
import { registry } from '@web/core/registry';
import { deserializeDateTime, formatDate } from '@web/core/l10n/dates';
import { rpc } from '@web/core/network/rpc';
import { session } from '@web/session';
import wSaleUtils from '@website_sale/js/website_sale_utils';
import daterangePickerUtils from '@website_sale_renting/js/daterange_picker_utils';

export class CartSummary extends Interaction {
    static selector = '.o_wsale_shorter_cart_summary';
    dynamicContent = {
        '.o_website_sale_daterange_picker': {
            't-on-daterange_picker_applied': this.onDaterangePickerApplied,
        },
    };

    /**
     * @param {CustomEvent} event
     */
    async onDaterangePickerApplied(event) {
        const { startDate, endDate } = event.detail;
        if (startDate && endDate) {
            const daterangePicker = event.currentTarget;
            const { start_date, end_date, warning, values } = await this.waitFor(rpc(
                '/shop/cart/update_renting',
                daterangePickerUtils.getSerializedRentalDates(daterangePicker),
            )) ?? {};
            if (!values) {
                return;
            }

            values['website_sale.cart_lines'] = markup(values['website_sale.cart_lines']);

            const cart = document.querySelector('#shop_cart');
            // `updateCartNavBar` regenerates the cart lines, so we need to stop and start
            // interactions to make sure the regenerated cart lines are properly handled.
            this.services['public.interactions'].stopInteractions(cart);
            wSaleUtils.updateCartNavBar(values);
            this.services['public.interactions'].startInteractions(cart);
            this.services.cart.showWarning(warning);
            // Deserialize into the website timezone for proper formatting.
            daterangePicker.querySelector('input[name=renting_start_date]').value = formatDate(
                deserializeDateTime(start_date, { tz: session.website_tz }),
                { tz: session.website_tz },
            );
            daterangePicker.querySelector('input[name=renting_end_date]').value = formatDate(
                deserializeDateTime(end_date, { tz: session.website_tz }),
                { tz: session.website_tz },
            );
        }
    }
}

registry
    .category('public.interactions')
    .add('website_sale_renting.cart_summary', CartSummary);

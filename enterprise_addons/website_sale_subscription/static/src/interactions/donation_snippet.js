import { patch } from "@web/core/utils/patch";
import { DonationSnippet } from "@website_sale/snippets/s_donation/donation_snippet";
import { _t } from "@web/core/l10n/translation";
import { renderToElement } from "@web/core/utils/render";

patch(DonationSnippet.prototype, {
    start() {
        super.start(...arguments);
        this.injectRecurrenceSelector();
    },

    injectRecurrenceSelector() {
        const plans = this.donationInfo?.plans || [];
        if (!plans.length) {
            return;
        }
        if (this.el.querySelector(".s_donation_recurrence_select")) {
            return;
        }
        const options = [{ id: "", name: _t("Once") }, ...plans];
        const recurrenceDropdownEl = renderToElement(
            "website_sale_subscription.donation.recurrenceSelect",
            { ariaLabel: _t("Recurrence"), options }
        );
        recurrenceDropdownEl.querySelectorAll(".dropdown-item").forEach((itemEl) => {
            itemEl.addEventListener("click", () => {
                recurrenceDropdownEl.querySelector(".s_donation_recurrence_select").value =
                    itemEl.dataset.value || "";
                recurrenceDropdownEl.querySelector(".dropdown-toggle").textContent =
                    itemEl.textContent.trim();
                recurrenceDropdownEl.querySelectorAll(".dropdown-item").forEach((el) =>
                    el.classList.toggle("active", el === itemEl)
                );
            });
        });
        this.insert(recurrenceDropdownEl, this.el.querySelector(".s_donation_donate_btn"), "beforebegin");
    },

    /**
     * Override of `website_sale` to switch to the recurring donation product when a plan is
     * selected, and to pass the plan id to the cart service.
     *
     * @param {number} amount - The donation amount
     * @returns {Object} The parameters to pass to the cart service
     */
    _getDonationCartParams(amount) {
        const recurrenceSelectEl = this.el.querySelector(".s_donation_recurrence_select");
        const planId = recurrenceSelectEl?.value ? parseInt(recurrenceSelectEl.value, 10) : null;
        if (planId) {
            return {
                ...super._getDonationCartParams(amount),
                productTemplateId: this.donationInfo.recurring_product_template_id,
                productId: this.donationInfo.recurring_product_id,
                plan_id: planId,
            };
        }
        return super._getDonationCartParams(amount);
    },
});

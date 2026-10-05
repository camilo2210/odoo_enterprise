import { Interaction } from '@web/public/interaction';
import { registry } from '@web/core/registry';

export class InvoicingInfo extends Interaction {
    static selector = "#form_l10n_mx_invoicing_info";
    dynamicSelectors = {
        ...this.dynamicSelectors,
        _submitButtons: () => document.querySelectorAll('[name="website_sale_main_button"]'),
    };
    dynamicContent = {
        // No invoice needed, submit right away.
        'button[data-need-invoice="0"]': { 't-on-click': this.locked(() => this.onClickNoInvoice(), true) },
        'button[data-need-invoice="1"]': { 't-on-click': () => this.updateNeedInvoice(true) },
        _submitButtons: { 't-on-click.prevent': this.locked(() => this.onSubmit(), true) },
    };

    setup() {
        this.needInvoiceInput = this.el.querySelector('input[name="need_invoice"]');
        this.additionalFields = this.el.querySelector('.div_l10n_mx_edi_additional_fields');
        this.updateNeedInvoice(this.needInvoiceInput.value === '1');
    }

    onClickNoInvoice() {
        this.updateNeedInvoice(false);
        this.onSubmit();
    }

    updateNeedInvoice(needInvoice) {
        this.needInvoiceInput.value = needInvoice ? '1' : '0';
        this.additionalFields.style.display = needInvoice ? '' : 'none';
        // Only require the additional fields when an invoice is requested, so the
        // native validation doesn't block submission when it's not needed.
        for (const field of this.additionalFields.querySelectorAll('.o_l10n_mx_required_field')) {
            field.required = needInvoice;
        }
    }

    onSubmit() {
        // Enforce the required fields through the native form validation.
        if (this.el.reportValidity()) {
            this.el.submit();
        }
    }
}

registry
    .category('public.interactions')
    .add('l10n_mx_edi_website_sale.invoicing_info', InvoicingInfo);

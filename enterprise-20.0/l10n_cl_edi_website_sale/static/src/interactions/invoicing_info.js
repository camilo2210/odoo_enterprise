import { Interaction } from '@web/public/interaction';
import { registry } from '@web/core/registry';

export class InvoicingInfo extends Interaction {
    static selector = "#form_l10n_cl_invoicing_info";
    dynamicSelectors = {
        ...this.dynamicSelectors,
        _submitButtons: () => document.querySelectorAll('[name="website_sale_main_button"]'),
    };
    dynamicContent = {
        'input[name="l10n_cl_type_document"]': { 't-on-click': this.onClTypeDocumentClick },
        _submitButtons: { 't-on-click.prevent': this.locked(() => this.el.submit(), true) },
    };

    setup() {
        if (document.getElementById('div_l10n_cl_additional_fields')) {
            this.onClTypeDocumentClick();
        }
    }

    /**
     * Event click, hidden fields l10n_cl_activity_description
     * if l10n_cl_sii_taxpayer_type is 'ticket'
     */
    onClTypeDocumentClick() {
        const typeDocumentEl = document.querySelector('input[name="l10n_cl_type_document"]');
        document.getElementById("div_l10n_cl_additional_fields")
            .style.display = typeDocumentEl.checked ? 'none' : '';
    }
}

registry
    .category('public.interactions')
    .add('l10n_cl_edi_website_sale.invoicing_info', InvoicingInfo);

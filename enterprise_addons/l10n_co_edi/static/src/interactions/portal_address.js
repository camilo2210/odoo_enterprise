import { patch } from '@web/core/utils/patch';
import { patchDynamicContent } from '@web/public/utils';
import { CustomerAddress } from '@portal/interactions/address';
import { SelectMenuWrapper } from '@l10n_co_edi/components/select_menu_wrapper/select_menu_wrapper';

patch(CustomerAddress.prototype, {
    setup() {
        super.setup();
        patchDynamicContent(this.dynamicContent, {
            'input[id="o_vat"]': {
                't-on-input': this.onChangeIdentificationType.bind(this),
            },
        });

        this.isColombianCompany = this.countryCode === 'CO';
        this.vat = this.addressForm['o_vat'];
    },

    start() {
        super.start();
        if (!this.isColombianCompany || !this.vat) return;

        const typeSelect = this.el.querySelector('select[name="l10n_co_edi_obligation_type_ids"]');
        this.mountComponent(typeSelect.parentElement, SelectMenuWrapper, { el: typeSelect });
        this.onChangeIdentificationType();
    },

    onChangeIdentificationType() {
        if (!this.isColombianCompany || !this.vat) return;

        if (this.vat.value) {
            this._showInput('l10n_co_edi_obligation_type_ids');
            this._showInput('l10n_co_edi_fiscal_regimen');
        } else {
            this._hideInput('l10n_co_edi_obligation_type_ids', false);
            this._hideInput('l10n_co_edi_fiscal_regimen', false);
        }
    },

});

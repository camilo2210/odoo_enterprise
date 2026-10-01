import { registry } from "@web/core/registry";
import { formView } from "@web/views/form/form_view";
import { FormRenderer } from "@web/views/form/form_renderer";

import { ExtractMixinFormRenderer } from '@iap_extract/components/manual_correction/form_renderer';


export class AccountLoanFormRenderer extends ExtractMixinFormRenderer(FormRenderer) {
    setup() {
        super.setup();

        this.recordModel = 'account.loan';
    }
};


export const AccountLoanFormViewExtract = {
    ...formView,
    Renderer: AccountLoanFormRenderer,
};

registry.category("views").add("account_loan_form", AccountLoanFormViewExtract);

<?xml version="1.0" encoding="UTF-8" ?>
<templates>
    <t t-name="l10n_ae_faf.company_data_warning">
        Please define the following for
        <a type="action" t-on-click="(ev) => this.controller.reportAction(ev, 'action_fill_company_details', warningParams)">
            your company
        </a>
        :
        <t t-out="warningParams.args"/>
    </t>
</templates>

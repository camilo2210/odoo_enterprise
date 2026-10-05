/** @odoo-module **/

import { useSubEnv } from "@web/owl2/utils";
import { Component, proxy, useProps } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useSetupAction } from "@web/search/action_hook";
import { Layout } from "@web/search/layout";
import { getDefaultConfig } from "@web/views/view";
import { standardActionServiceProps } from "@web/webclient/actions/action_plugin";
import { user } from "@web/core/user";

export class SwissdecInteroperabilityClient extends Component {
    props = useProps(standardActionServiceProps);
    static template = "l10n_ch_hr_payroll.SwissdecInteroperabilityClient";
    static components = { Layout };

    setup() {
        useSubEnv({
            config: {
                ...getDefaultConfig(),
                ...this.env.config,
            },
        });
        useSetupAction();
        this.orm = useService("orm");
        this.company = user.activeCompany;
        this.state = proxy({
            ping_response: false,
            check_interoperability_response: false,
            second_operand: "",
            loading: false,
        });
    }

    async PingRequest(){
        await this.request(async () => {
            this.state.ping_response = await this.orm.call('res.company', 'l10n_ch_hr_payroll_action_ping', [[this.company.id]]);
        });
    }

    async CheckInteroperabilityRequest(ev){
        await this.request(async () => {
            this.state.check_interoperability_response = await this.orm.call('res.company', 'l10n_ch_hr_payroll_action_check_interoperability', [
                [this.company.id],
                this.state.second_operand
            ]);
        });
    }

    async request(callback) {
        this.state.loading = true;
        try {
            await callback();
        } finally {
            this.state.loading = false;
        }
    }

    onOperandInput(ev){
        this.state.second_operand = ev.target.value
    }
}

registry.category("actions").add("swissdec_interoperability_client", SwissdecInteroperabilityClient);

import { Component, t, useProps } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { getEmbeddedProps } from "@html_editor/others/embedded_component_utils";
import { useService } from "@web/core/utils/hooks";

export class AccountReportComponent extends Component {
    static template = "accountant_knowledge.EmbeddedAccountReport";

    props = useProps({
        host: t.object(),
        name: t.string(),
        options: t.object(),
    });

    setup() {
        this.actionService = useService("action");
    }
    /** @returns {Promise} */
    openAccountReport() {
        return this.actionService.doAction({
            type: "ir.actions.client",
            tag: "account_report",
            name: this.props.name,
            params: {
                ignore_session: true,
                options: this.props.options,
            },
            context: {
                html_element_host_id: this.props.host.dataset.oeId,
                article_id: this.env.model.root.resId,
                report_id: this.props.options.report_id,
            },
        });
    }
}

export const accountReportEmbedding = {
    name: "accountReport",
    Component: AccountReportComponent,
    getProps: (host) => {
        const props = {
            ...getEmbeddedProps(host),
            host
        };
        if (props.name) {
            props.name = _t(props.name);
        }
        return props;
    },
};

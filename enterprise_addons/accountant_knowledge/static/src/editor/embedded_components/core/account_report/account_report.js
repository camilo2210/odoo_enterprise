import { Component, t, useProps } from "@odoo/owl";
import { getEmbeddedProps } from "@html_editor/others/embedded_component_utils";

export class ReadonlyAccountReportComponent extends Component {
    static template = "accountant_knowledge.ReadonlyEmbeddedAccountReport";

    props = useProps({
        name: t.string(),
        options: t.object(),
    });

}

export const readonlyAccountReportEmbedding = {
    name: "accountReport",
    Component: ReadonlyAccountReportComponent,
    getProps: (host) => ({
        ...getEmbeddedProps(host),
    }),
};

import { Component, onWillStart, proxy } from "@odoo/owl";
import { ReportEditorIframe } from "../report_editor_iframe";

export class ReportEditorPreview extends Component {
    static components = { ReportEditorIframe };
    static template = "web_studio.ReportEditorPreview";

    setup() {
        this.reportEditorModel = proxy(this.env.reportEditorModel);
        onWillStart(() => this.reportEditorModel.loadReportHtml());
    }
}

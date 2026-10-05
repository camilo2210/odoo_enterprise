import { SignInfoPlugin } from "@sign/services/sign_info_plugin";
import { useService } from "@web/core/utils/hooks";
import { onWillStart, usePlugin } from "@odoo/owl";
import { SignRefusalDialog, DelegateSignDialog } from "@sign/dialogs/dialogs";
import { rpc } from "@web/core/network/rpc";
import { SignRequestControlPanel } from "@sign/backend_components/sign_request/sign_request_control_panel";

export class SignableRequestControlPanel extends SignRequestControlPanel {
    static template = "sign.SignSignableRequestControlPanel";

    setup() {
        super.setup();
        this.controlPanelDisplay = {};
        this.action = useService("action");
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.signInfo = usePlugin(SignInfoPlugin);

        this.documentId = this.signInfo.get("documentId");
        this.signRequestToken = this.signInfo.get("signRequestToken");
        this.originalDocuments = [];

        onWillStart(async () => {
            const { original_documents } = await rpc(
                `/sign/get_original_documents/${this.documentId}/${this.signRequestToken}`
            );
            this.originalDocuments = original_documents;
        });
    }

    refuseDocument() {
        this.dialog.add(SignRefusalDialog);
    }

    downloadDocument() {
        const downloadUrl = `/sign/download/${this.documentId}/${this.signRequestToken}/origin/`;
        const url =
            this.originalDocuments.length === 1
                ? downloadUrl + this.originalDocuments[0].id
                : downloadUrl;

        return this.action.doAction({
            type: "ir.actions.act_url",
            target: "download",
            url,
        });
    }

    delegateDocument() {
        this.dialog.add(DelegateSignDialog);
    }

    // hide 'Details' button in signing mode.
    get shouldShowDetailsButton() {
        return false;
    }

    get showResendButtons() {
        return false;
    }

    get templateHeaderTagsProps() {
        return false;
    }

    get shouldShowDownloadDropdown() {
        return false;
    }
}

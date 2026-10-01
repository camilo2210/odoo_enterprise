import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { patch } from "@web/core/utils/patch";
import { Document } from "@sign/components/sign_request/document_signable";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { ItsmeDialog } from "@sign_itsme/dialogs/itsme_dialog";


patch(Document.prototype, {
    async getAuthDialog() {
        if (this.authMethod === "itsme" || this.authMethod === "itsme_qes") {
            // a qualified signature can never fall back to signing without itsme.
            // always open the dialog and let the server enforce the credit check
            const credits =
                this.authMethod === "itsme_qes" || (await rpc("/itsme/has_itsme_credits"));
            if (credits) {
                const [route, params] = await this._getRouteAndParams();
                const props = {
                    route,
                    params,
                    isQualifiedSignature: this.authMethod === "itsme_qes",
                    onSuccess: () => {
                        this.openThankYouDialog();
                    },
                };
                return {
                    component: ItsmeDialog,
                    props,
                };
            }
        }
        return super.getAuthDialog();
    },

    getDataFromHTML() {
        if (!super.getDataFromHTML()) {
            return false;
        }
        const parentEl = this.props.parent();
        this.errorMessage = parentEl.querySelector("#o_sign_show_error_message")?.value;
        if (this.errorMessage) {
            const [errorMessage, title] = processErrorMessage(this.errorMessage);
            this.dialog.add(
                AlertDialog,
                { title: title || _t("Error"), body: errorMessage },
                { onClose: () => deleteQueryParamFromURL("error_message") }
            );
        }
        return true;
    },
});

function deleteQueryParamFromURL(param) {
    const url = new URL(location.href);
    url.searchParams.delete(param);
    window.history.replaceState(null, "", url);
}

/**
 * Processes special errors from the IAP server
 * @param { String } errorMessage
 * @returns { [String, Boolean] } error message, title or false
 */
function processErrorMessage(errorMessage) {
    const defaultTitle = false;
    const errorMap = {
        err_connection_odoo_instance: [
            _t(
                "The itsme® identification data could not be forwarded to Odoo, the signature could not be saved."
            ),
            defaultTitle,
        ],
        access_denied: [
            _t(
                "You have rejected the identification request or took too long to process it. You can try again to finalize your signature."
            ),
            _t("Identification refused"),
        ],
    };
    return errorMap[errorMessage] ? errorMap[errorMessage] : [errorMessage, defaultTitle];
}

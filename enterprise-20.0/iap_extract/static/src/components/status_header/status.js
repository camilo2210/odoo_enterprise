import {
    Component,
    onWillDestroy,
    onWillStart,
    proxy,
    useEffect,
    useOnChange,
    useProps,
} from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

const CHECK_OCR_WAIT_DELAY = 5 * 1000;

export class StatusHeader extends Component {
    static template = "account_invoice_extract.Status";

    props = useProps(standardFieldProps);

    setup() {
        this.state = proxy({
            status: this.props.record.data.extract_state,
            errorMessage: this.props.record.data.extract_error_message,
            retryLoading: false,
            checkStatusLoading: false,
        });
        this.orm = useService("orm");
        this.action = useService("action");
        this.busService = this.env.services.bus_service;

        useEffect(() => {
            const extract_status = this.props.record.data.extract_state;
            if (extract_status !== this.state.status) {
                this.state.status = extract_status;
                this.state.errorMessage = this.props.record.data.extract_error_message;
            }
        });
        useEffect(() => {
            const extract_document_uuid = this.props.record.data.extract_document_uuid;
            if (extract_document_uuid && !this.channelName) {
                this.subscribeToChannel(extract_document_uuid);
                this.enableTimeout();
            }
        });

        onWillStart(() => {
            // When a new document is uploaded (via the Upload button, or by attaching a file),
            // the server will send a `extract_mixin_new_document` message on the bus with the
            // `extract_document_uuid` created upon submitting the document to the OCR server.
            // We can then subscribe for state changes event of this document uuid
            // (typically when OCR has finished processing it)
            this.busService.subscribe("extract_mixin_new_document", (params) => {
                this.state.status = params.status;
                this.state.errorMessage = params.error_message;
                this.subscribeToChannel(params.extract_document_uuid);
            });
            this.busService.subscribe("state_change", ({ status, error_message }) => {
                this.state.status = status;
                this.state.errorMessage = error_message;
            });
        });

        onWillDestroy(() => {
            this.busService.deleteChannel(this.channelName);
            this.state.status = "no_extract_requested";
            clearTimeout(this.timeoutId);
        });

        useOnChange(
            () => [this.props.record.id],
            () => {
                const record = this.props.record;
                this.state.errorMessage = record.data.extract_error_message;
                this.state.status = record.data.extract_state;
                this.subscribeToChannel(record.data.extract_document_uuid);
                this.enableTimeout();
            },
            { initialRun: false }
        );
    }

    subscribeToChannel(documentUUID) {
        if (!documentUUID) {
            return;
        }
        this.busService.deleteChannel(this.channelName);
        this.channelName = `extract.mixin.status#${documentUUID}`;
        this.busService.addChannel(this.channelName);
    }

    enableTimeout() {
        if (!["waiting_extraction", "extract_not_ready"].includes(this.state.status)) {
            return;
        }

        clearTimeout(this.timeoutId);

        this.timeoutId = setTimeout(async () => {
            if (["waiting_extraction", "extract_not_ready"].includes(this.state.status)) {
                const [status, errorMessage] = (
                    await this.orm.call(
                        this.props.record.resModel,
                        "check_ocr_status",
                        [this.props.record.resId],
                        {}
                    )
                )[0];
                this.state.status = status;
                this.state.errorMessage = errorMessage;
            }
        }, CHECK_OCR_WAIT_DELAY);
    }

    async checkOcrStatus() {
        this.state.checkStatusLoading = true;
        const [status, errorMessage] = (
            await this.orm.call(
                this.props.record.resModel,
                "check_ocr_status",
                [this.props.record.resId],
                {}
            )
        )[0];
        if (["waiting_validation", "to_validate", "done"].includes(status)) {
            await this.refreshPage();
            return;
        }
        this.state.status = status;
        this.state.errorMessage = errorMessage;
        this.state.checkStatusLoading = false;
    }

    async refreshPage() {
        return this.props.record.model.load();
    }

    async buyCredits() {
        const actionData = await this.orm.call(
            this.props.record.resModel,
            "buy_credits",
            [this.props.record.resId],
            {}
        );
        this.action.doAction(actionData);
    }

    async retryDigitalization() {
        this.state.retryLoading = true;
        const [status, errorMessage, documentUUID] = await this.orm.call(
            this.props.record.resModel,
            "action_manual_send_for_digitization",
            [this.props.record.resId],
            {}
        );
        this.subscribeToChannel(documentUUID);
        this.state.status = status;
        this.state.errorMessage = errorMessage;
        this.state.retryLoading = false;
        this.enableTimeout();
    }
}

registry.category("fields").add("extract_state_header", { component: StatusHeader });

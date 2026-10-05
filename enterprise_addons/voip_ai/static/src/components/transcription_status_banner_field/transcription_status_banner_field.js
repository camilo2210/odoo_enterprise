import { useProps, proxy } from "@odoo/owl";

import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { SelectionField } from "@web/views/fields/selection/selection_field";

const BANNERS = {
    pending: {
        class: "alert-warning",
        text: _t("Transcription pending..."),
        hasButton: true,
    },
    error: {
        class: "alert-danger",
        text: _t("This call's transcription led to an error. It is not available."),
    },
};

export class TranscriptionStatusBannerField extends SelectionField {
    static template = "voip_ai.TranscriptionStatusBannerField";
    props = useProps();

    setup() {
        super.setup();
        this.notification = useService("notification");
        this.state = proxy({ loading: false, requestSent: false });
    }

    get banner() {
        return BANNERS[this.props.record.data.transcription_state] || null;
    }

    onClickTranscribe() {
        if (this.state.loading || this.state.requestSent) {
            return;
        }
        this.state.loading = true;

        rpc("/ai/transcription/call", {
            call_model: this.props.record.resModel,
            call_id: this.props.record.resId,
        })
            .then(() => {
                this.state.requestSent = true;
                return this.props.record.load();
            })
            .catch(() => {
                this.state.requestSent = false;
                this.notification.add(_t("Transcription failed"), { type: "danger" });
            })
            .finally(() => {
                this.state.loading = false;
            });
    }
}

registry.category("fields").add("voip_ai_transcription_state_banner", {
    component: TranscriptionStatusBannerField,
    displayName: _t("Transcription Status Banner"),
    supportedTypes: ["selection"],
});

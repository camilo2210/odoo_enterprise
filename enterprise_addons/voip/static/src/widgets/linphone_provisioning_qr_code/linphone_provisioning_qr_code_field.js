import { Component, onWillDestroy, proxy, t, useProps } from "@odoo/owl";
import { isMobileOS } from "@web/core/browser/feature_detection";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

// Mirrors PROVISIONING_URI_SCHEME in voip/tools/linphone.py: the scheme
// liblinphone claims so that following a link applies a provisioning document.
const PROVISIONING_URI_SCHEME = "linphone-config:";

const ROTATED_NOTIFICATION = "voip.linphone_provisioning/rotated";

export class VoipLinphoneProvisioningQrCodeField extends Component {
    static template = "voip.LinphoneProvisioningQrCodeField";
    props = useProps({
        ...standardFieldProps,
        size: t.number().optional(176),
        urlField: t.string(),
    });

    setup() {
        this.orm = useService("orm");
        this.state = proxy({ rotated: null });
        this.onRotated = () => this.refresh();
        const busService = useService("bus_service");
        busService.subscribe(ROTATED_NOTIFICATION, this.onRotated);
        onWillDestroy(() => busService.unsubscribe(ROTATED_NOTIFICATION, this.onRotated));
    }

    get fieldNames() {
        return [this.props.name, this.props.urlField];
    }

    get qrCode() {
        return this.value(this.props.name);
    }

    /** Only where an installed Linphone can claim the scheme. */
    get deepLink() {
        return isMobileOS()
            ? `${PROVISIONING_URI_SCHEME}${this.value(this.props.urlField)}`
            : false;
    }

    value(fieldName) {
        return this.state.rotated?.[fieldName] ?? this.props.record.data[fieldName];
    }

    /**
     * Serving the document a code points to bumps the provisioning serial,
     * which invalidates every URL issued before it: the code on screen is dead
     * the moment a phone reads it. Only the two fields are re-read, never the
     * whole record, which may be carrying edits the user has not saved yet.
     */
    async refresh() {
        const record = this.props.record;
        const [values] = await this.orm.read(record.resModel, [record.resId], this.fieldNames);
        this.state.rotated = values;
    }
}

export const voipLinphoneProvisioningQrCodeField = {
    component: VoipLinphoneProvisioningQrCodeField,
    displayName: _t("Linphone Provisioning QR Code"),
    supportedTypes: ["char"],
    supportedOptions: [
        {
            label: _t("Size"),
            name: "size",
            type: "number",
        },
        {
            label: _t("Provisioning link field"),
            name: "url_field",
            type: "field",
        },
    ],
    extractProps: ({ options }) => ({ size: options.size, urlField: options.url_field }),
};

registry
    .category("fields")
    .add("voip_linphone_provisioning_qr_code", voipLinphoneProvisioningQrCodeField);

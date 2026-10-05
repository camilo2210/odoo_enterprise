import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { buildM2OFieldDescription, Many2OneField } from "@web/views/fields/many2one/many2one_field";

class CertificateM2OWidget extends Many2OneField {
    setup() {
        this.action = useService("action");
    }

    get m2oProps() {
        return {
            ...super.m2oProps,
            createAction: () => this._openCertificateWizard(),
        };
    }

    async _openCertificateWizard() {
        const record = this.props.record;
        return this.action.doAction({
            type: "ir.actions.act_window",
            name: "Signing certificate",
            res_model: "certificate.wizard",
            views: [[false, "form"]],
            target: "new",
            }, {
                    onClose: async (cert_id) => {
                        // If the wizard returned a value (the new cert ID)
                        if (typeof cert_id === 'number') {
                            // Update the field in the UI record
                            await record.update({ ['signing_certificate_id']: { id: cert_id } });
                        }
                    }
            }
        );
    }
}

registry.category("fields").add("certificateM2OWidget", {
    ...buildM2OFieldDescription(CertificateM2OWidget),
});

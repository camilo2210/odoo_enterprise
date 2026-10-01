import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { CertifiedScaleScreen } from "@l10n_eu_iot_scale_cert/app/components/certified_scale_screen/certified_scale_screen";

patch(PosStore.prototype, {
    async processServerData() {
        await super.processServerData(...arguments);

        this.isScaleIconVisible =
            this.config._is_eu_country &&
            this.models["product.product"].some((product) => product.to_weight);

        this.config.isCertified = this.isCertified;
        this.config.showCertificationWarning = this.isScaleIconVisible && !this.isCertified;
    },

    get decimalAccuracy() {
        return this.models["decimal.precision"].find((dp) => dp.name === "Product Unit");
    },

    get certificationErrors() {
        const errors = [];
        if (this.config._scale_checksum !== this.config._scale_checksum_expected) {
            errors.push(
                _t("Checksum does not match, the code has been modified and is no longer certified")
            );
        }
        if (this.decimalAccuracy.digits < 3) {
            errors.push(_t("Decimal accuracy is less than 3 decimal places"));
        }
        return errors;
    },

    get isCertified() {
        return this.certificationErrors.length === 0;
    },

    async handleWeighableProduct(values, order, configure) {
        if (values.product_tmpl_id.to_weight && this.scale && configure && this.isScaleIconVisible) {
            const productUomId = values.product_id.product_tmpl_id?.uom_id?.id;
            if (productUomId !== this.config._kg_uom_id) {
                this.dialog.add(AlertDialog, {
                    title: _t("Unable to weigh product"),
                    body: _t("The unit of measure must be set to kg to weigh in a certified POS."),
                });
                return false;
            }
        }
        return super.handleWeighableProduct(...arguments);
    },

    async weighProduct() {
        // Returning 0 instead of null stops the POS still adding
        // an orderline in case of error (not desired behaviour when certified)
        return makeAwaitable(this.env.services.dialog, CertifiedScaleScreen);
    },
});

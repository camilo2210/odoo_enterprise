import { patch } from "@web/core/utils/patch";
import { Form } from "@website/snippets/s_website_form/form";

patch(Form.prototype, {
    getUserPreFillFields() {
        const fields = super.getUserPreFillFields();
        if (this.el.dataset.model_name === "planning.slot") {
            return [...fields, "street", "street2", "city", "zip", "country_id", "state_id"];
        }
        return fields;
    },

    async willStart() {
        await super.willStart();
        if (this.el.dataset.model_name === "planning.slot") {
            // res.users.read returns many2one fields as [id, display_name], unwrap id.
            for (const field of ["country_id", "state_id"]) {
                if (Array.isArray(this.preFillValues[field])) {
                    this.preFillValues[field] = this.preFillValues[field][0];
                }
            }
        }
    },
});

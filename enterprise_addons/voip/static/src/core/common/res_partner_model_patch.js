import { ResPartner } from "@mail/core/common/res_partner_model";
import { fields } from "@mail/model/export";

import { patch } from "@web/core/utils/patch";

patch(ResPartner.prototype, {
    setup() {
        super.setup(...arguments);
        this.phone_country_id = fields.One("res.country");
        /** @type {string|undefined} */
        this.phone_formatted = undefined;
        /** @type {string|undefined} */
        this.t9_name = undefined;
    },
    /**
     * Can be overridden to change the name.
     *
     * @returns {string}
     */
    get voipName() {
        return this.name || "";
    },
    get jobDescription() {
        const info = [];
        if (this.parent_name) {
            info.push(this.parent_name);
        }
        // ⚠ French: function = job position
        if (this.function) {
            info.push(this.function);
        }
        return info.join(" - ");
    },
});

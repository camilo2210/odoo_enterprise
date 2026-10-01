import { PosCategory } from "@point_of_sale/app/models/pos_category";
import { patch } from "@web/core/utils/patch";

patch(PosCategory.prototype, {
    get prepLines() {
        return this.models["pos.prep.line"].filter(
            (pl) => pl.stage_id && pl.categories.some((categ) => categ.id === this.id)
        );
    },
});

import { components } from "@odoo/o-spreadsheet";
import { patch } from "@web/core/utils/patch";
import { INSERT_COMMENT_ACTION } from "@spreadsheet_edition/bundle/comments/index";

const { Grid } = components;

patch(Grid.prototype, {
    setup() {
        super.setup();
        this.keyDownMapping["Ctrl+Alt+M"] =  () => INSERT_COMMENT_ACTION.execute?.(this.env);
    },
});

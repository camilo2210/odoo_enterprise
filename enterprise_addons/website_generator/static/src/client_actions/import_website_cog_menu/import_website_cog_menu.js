import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { useService } from "@web/core/utils/hooks";

import { Component } from "@odoo/owl";

// Base template to be reused for in website_generator_sale and website_generator_blog
export class ImportWebsiteCogMenu extends Component {
    static template = "website_generator.import_website_cog_menu";
    static components = { DropdownItem };

    setup() {
        this.dialog = useService("dialog");
    }
}

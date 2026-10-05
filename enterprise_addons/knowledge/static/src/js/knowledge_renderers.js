import { useListener } from "@odoo/owl";
import { FormRenderer } from "@web/views/form/form_renderer";

export class KnowledgeArticleFormRenderer extends FormRenderer {

    //--------------------------------------------------------------------------
    // Component
    //--------------------------------------------------------------------------
    setup() {
        super.setup();
        useListener(document, "click", event => {
            if (event.target.classList.contains("o_nocontent_create_btn")) {
                this.env.createArticle("private");
            }
        });
    }
}

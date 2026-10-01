import { patch } from "@web/core/utils/patch";
import { KnowledgeArticleFormController } from "@knowledge/js/knowledge_controller";


patch(KnowledgeArticleFormController.prototype, {
    getKnowledgeCoverDialogProps(){
        let props = super.getKnowledgeCoverDialogProps();
        props['coverImagePath'] = this.model.root.data.cover_image_url;
        return props;
    },
})

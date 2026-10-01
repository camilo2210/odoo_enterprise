import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import {
    BooleanFavoriteField,
    booleanFavoriteField,
} from "@web/views/fields/boolean_favorite/boolean_favorite_field";

export class DocumentFavoriteField extends BooleanFavoriteField {
    setup() {
        super.setup();
        this.documentService = useService("document.document");
    }

    /** Override **/
    async update() {
        if (this.props.readonly) {
            return;
        }
        await this.documentService.toggleFavorites([this.props.record.resId]);
    }
}

export const documentFavoriteField = {
    ...booleanFavoriteField,
    component: DocumentFavoriteField,
};

registry.category("fields").add("document_favorite", documentFavoriteField);

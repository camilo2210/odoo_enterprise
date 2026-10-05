import { FormStatusIndicator } from "@web/views/form/form_status_indicator/form_status_indicator";

/**
 * Extends the standard FormStatusIndicator to restyle the save/discard buttons
 * so they fit the Knowledge topbar.
 */
export class KnowledgeFormStatusIndicator extends FormStatusIndicator {
    static template = 'knowledge.FormStatusIndicator';
}

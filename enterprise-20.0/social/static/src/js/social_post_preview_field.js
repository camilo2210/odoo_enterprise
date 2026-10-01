import { SocialPostFormatterMixin } from "./social_post_formatter_mixin";

import { HtmlField, htmlField, htmlFieldProps } from "@html_editor/fields/html_field";
import { getInnerHtml } from "@mail/utils/common/html";
import { registry } from "@web/core/registry";
import { createDocumentFragmentFromContent } from "@web/core/utils/html";
import { HtmlViewer } from "@html_editor/components/html_viewer/html_viewer";

import { useProps, t } from "@odoo/owl";

class SocialHtmlViewer extends HtmlViewer {
    retargetLink() {}
}

export class FieldPostPreview extends SocialPostFormatterMixin(HtmlField) {
    props = useProps({
        ...htmlFieldProps,
        mediaType: t.string().optional(),
    });
    static components = {
        ...HtmlField.components,
        HtmlViewer: SocialHtmlViewer,
    };

    get value() {
        const value = this.props.record.data[this.props.name] || "";
        const html = createDocumentFragmentFromContent(value);
        for (const previewMessage of html.querySelectorAll(".o_social_preview_message")) {
            previewMessage.innerHTML = this._formatPost(previewMessage.textContent.trim());
        }
        return getInnerHtml(html.body);
    }
}

export const fieldPostPreview = {
    ...htmlField,
    component: FieldPostPreview,
    extractProps({ attrs }) {
        const props = htmlField.extractProps(...arguments);
        props.mediaType = attrs.media_type || "";
        return props;
    },
};

registry.category("fields").add("social_post_preview", fieldPostPreview);

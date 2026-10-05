import { Component, useProps } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class ExplanationTooltip extends Component {
    static template = "hr_payroll.ExplanationTooltip";

    props = useProps(standardFieldProps);

    get textContent() {
        return this.extractTextFromHtml(this.props.record.data[this.props.name]);
    }

    extractTextFromHtml(htmlContent) {
        const parser = new DOMParser();
        const contentDocument = parser.parseFromString(htmlContent, "text/html");

        // Extract text with proper spacing between block elements
        const blockElements = contentDocument.body.querySelectorAll(
            "p, div, h1, h2, h3, h4, h5, h6, blockquote, li"
        );
        const textParts = [];

        if (blockElements.length > 0) {
            blockElements.forEach((el) => {
                const text = el.textContent.trim();
                if (text) {
                    textParts.push(text);
                }
            });
            return textParts.join("\n");
        }
        return contentDocument.body.textContent?.trim() || "";
    }
}

export const explanationTooltip = {
    component: ExplanationTooltip,
};

registry.category("fields").add("explanation_tooltip", explanationTooltip);

import { BaseOptionComponent } from "@html_builder/core/base_option_component";
import { markup, t, useProps } from "@odoo/owl";

export class ImportedFooterTemplateChoice extends BaseOptionComponent {
    static template = "website_generator.ImportedFooterTemplateChoice";

    props = useProps({
        title: t.string(),
        view: t.string(),
        varName: t.string(),
        imgSrc: t.string(),
    });

    setup() {
        this.label = markup`<Image attrs="{ style: 'width: 100%;' }" src="${this.props.imgSrc}"/>`;
    }
}

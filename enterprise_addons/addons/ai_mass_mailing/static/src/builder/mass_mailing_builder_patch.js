import { patch } from "@web/core/utils/patch"
import { MassMailingBuilder } from "@mass_mailing/builder/mass_mailing_builder"
import { AIImagePlugin } from "@ai/core/html_editor/ai_image_plugin";

patch(MassMailingBuilder.prototype, {
    get builderProps(){
        let props = super.builderProps;
        props.Plugins = [...props.Plugins, AIImagePlugin];
        return props;
    }
})

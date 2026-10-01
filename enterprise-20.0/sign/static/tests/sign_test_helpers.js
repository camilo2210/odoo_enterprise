import { models, fields } from "@web/../tests/web_test_helpers";

export class SignTemplateTag extends models.Model {
    _name = "sign.template.tag";
    name = fields.Char();
    color = fields.Integer();
}

export class SignTemplate extends models.Model {
    _name = "sign.template";
    tag_ids = fields.Many2many({ relation: "sign.template.tag" });
}

export class SignRequest extends models.Model {
    _name = "sign.request";
    template_tags = fields.Many2many({ relation: "sign.template.tag" });
    _records = [
        {
            id: 5,
            template_tags: [],
        },
    ];
}

import { defineModels } from "@web/../tests/web_test_helpers";
import { mailModels } from "@mail/../tests/mail_test_helpers";
import { hootPosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";

export const defineL10nCLPosEdiModels = () => {
    const posModelNames = hootPosModels.map((modelClass) => modelClass.prototype.constructor._name);
    const modelsFromMail = Object.values(mailModels).filter(
        (modelClass) => !posModelNames.includes(modelClass.prototype.constructor._name)
    );
    defineModels([...modelsFromMail, ...hootPosModels]);
};

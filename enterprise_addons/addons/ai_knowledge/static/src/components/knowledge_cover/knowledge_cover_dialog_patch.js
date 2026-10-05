import { useDataGetter } from "@ai/utils/bus_data_getter";
import { KnowledgeCoverDialog } from "@knowledge/components/knowledge_cover/knowledge_cover_dialog";
import { t, useProps } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";

patch(KnowledgeCoverDialog.prototype, {
    setup() {
        super.setup();

        this.aiKnowledgeProps = useProps({
            coverImagePath: t.string().optional(),
        });
        useDataGetter("mediaDialog", () => this.getMediaDialogData());
    },
    getMediaDialogData() {
        return {
            aiSpecialActions: {
                useThis: async ({ message, store }) => {
                    const orm = store.env.services.orm;
                    const imageAttachment = message.attachment_ids.filter((attachment) =>
                        attachment.mimetype.includes("image")
                    )[0];
                    const [coverId] = await orm.create("knowledge.cover", [
                        { attachment_id: imageAttachment.id },
                    ]);
                    await this.props.save(coverId);
                },
            },
            imagePath: this.aiKnowledgeProps.coverImagePath,
            mediaDialogCloseFunction: () => this.props.close(),
        };
    },
});

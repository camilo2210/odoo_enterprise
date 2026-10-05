import { _t } from "@web/core/l10n/translation";

export const STATUS_BADGE_CLASS = {
    indexed: "text-bg-success",
    incomplete: "text-bg-warning",
    processing: "text-bg-info",
    failed: "text-bg-danger",
};

export const SOURCE_ICON_CONFIGS = {
    url: () => ({
        type: "icon",
        icon: "link",
        title: _t("Link"),
    }),
    binary: (record) => {
        const { mimetype } = record.data;
        if (mimetype) {
            return {
                type: "mimetype",
                dataMimetype: mimetype,
                title: mimetype,
            };
        }
        return SOURCE_ICON_CONFIGS.default(record);
    },
    default: () => ({
        type: "icon",
        icon: "description",
        title: _t("File"),
    }),
};

import { patch } from "@web/core/utils/patch";
import { shareTargetService } from "@web/webclient/share_target/share_target_service";
import mobile from "@web_mobile/js/services/core";

patch(shareTargetService, {
    async _getShareTargetFiles() {
        if (!mobile.methods.getShareTargetFiles) {
            return super._getShareTargetFiles();
        }
        /**
         * {
         *   "success" : true,
         *   "data" : [
         *   {
         *     uri: "content://com.google.android.apps.nbu.files.provider/2/1000006851"
         *     name: "name.jpg"
         *     type: "image/jpeg",
         *   },
         *   ...]
         */
        const response = await mobile.methods.getShareTargetFiles();
        if (response.success) {
            const files = [];
            for (let i = 0; i < response.data.length; i++) {
                const { name, uri, type } = response.data[i];
                // this is a fake rpc call to mobile apps.
                // The app will stream the file content to avoid the risk of some Out of Memory
                const fakeRpc = await fetch(
                    `/share_target.localhost/?uri=${encodeURIComponent(uri)}`
                );
                if (!fakeRpc.ok) {
                    throw new Error(`Unable to share file: ${name}`);
                }
                const blob = await fakeRpc.blob();
                files.push(new File([blob], name, { type }));
            }
            return files;
        }
        return [];
    },
});

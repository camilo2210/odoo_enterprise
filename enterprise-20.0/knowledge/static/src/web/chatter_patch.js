import { useService } from "@web/core/utils/hooks";
import { KeepLast } from "@web/core/utils/concurrency";
import { patch } from "@web/core/utils/patch";
import { Chatter } from "@mail/chatter/web_portal_project/chatter";
import { useCallbackRecorder } from "@web/search/action_hook";
import { onMounted, onPatched, onWillUnmount } from "@odoo/owl";

/**
 * Knowledge articles can interact with some records with the help of the
 * @see KnowledgeCommandsService .
 * If any record in a form view has a chatter with the ability to send message
 * and/or attach files, they are a potential target for Knowledge macros.
 */
const ChatterPatch = {
    setup() {
        super.setup(...arguments);
        if (this.env.__knowledgeUpdateCommandsRecordInfo__) {
            this.knowledgeCommandsService = useService("knowledgeCommandsService");
            // Only keep the last request to register a recordInfo active.
            const keepLastRecordInfoRequest = new KeepLast();
            // Keep track of the fact that the chatter thread is ready and has
            // loaded its access rights.
            const { promise, resolve } = Promise.withResolvers();
            let chatterThreadReadyPromise = promise;
            let resolveChatterThreadReady = resolve;
            let previousThreadId = this.thread()?.id;
            // Access rights of the current thread of the chatter are populated
            // asynchronously (in place, on the mail record) after the chatter
            // is mounted, so they are not tracked by owl signals/effects. The
            // chatter re-renders when they change, so this runs on every mount
            // and patch to determine when a recordInfo request can be
            // evaluated.
            const updateChatterThreadReady = () => {
                const thread = this.thread();
                const threadId = thread?.id;
                if (previousThreadId !== threadId) {
                    // If the chatter changes threadId, resolve the current
                    // promise keeping track of the thread state to false, so
                    // that an ongoing request to evaluate a recordInfo (related
                    // to the previous thread) will be discarded.
                    resolveChatterThreadReady(false);
                    const { promise, resolve } = Promise.withResolvers();
                    chatterThreadReadyPromise = promise;
                    resolveChatterThreadReady = resolve;
                }
                if (
                    thread?.canPostOnReadonly !== undefined &&
                    thread?.hasReadAccess !== undefined &&
                    thread?.hasWriteAccess !== undefined
                ) {
                    // When the access rights are all loaded, the thread is
                    // ready and a recordInfo request can be evaluated.
                    resolveChatterThreadReady(true);
                }
                previousThreadId = threadId;
            };
            onMounted(updateChatterThreadReady);
            onPatched(updateChatterThreadReady);
            onWillUnmount(() => {
                // If there is an ongoing request to evaluate a recordInfo,
                // discard it.
                resolveChatterThreadReady(false);
            });
            useCallbackRecorder(
                this.env.__knowledgeUpdateCommandsRecordInfo__,
                // Callback used to record the values related to the ability to
                // post messages or attach files on the current record.
                async (recordInfo) => {
                    // At each new recording request, all previous ongoing
                    // requests are discarded through the keepLast.
                    const chatterThreadReadyForRecordInfo =
                        keepLastRecordInfoRequest.add(chatterThreadReadyPromise);
                    if (!(await chatterThreadReadyForRecordInfo)) {
                        // If the chatterThreadReadyForRecordInfo promise
                        // resolves to false, the recording request should be
                        // discarded.
                        return;
                    }
                    if (
                        !this.env.model.root?.resId ||
                        recordInfo.resId !== this.env.model.root.resId ||
                        recordInfo.resModel !== this.env.model.root.resModel
                    ) {
                        // Ensure that the current record matches the recordInfo
                        // candidate.
                        return;
                    }
                    // The conditions for the ability to post or attach should
                    // be the same as the ones in the Chatter template.
                    Object.assign(recordInfo, {
                        canPostMessages:
                            this.thread()?.id &&
                            (this.thread()?.hasWriteAccess ||
                                (this.thread()?.hasReadAccess && this.thread()?.canPostOnReadonly)),
                        canAttachFiles: this.thread()?.id && this.thread()?.hasWriteAccess,
                    });
                    if (this.knowledgeCommandsService.isRecordCompatibleWithMacro(recordInfo)) {
                        this.knowledgeCommandsService.setCommandsRecordInfo(recordInfo);
                    }
                }
            );
        }
    },
};

patch(Chatter.prototype, ChatterPatch);

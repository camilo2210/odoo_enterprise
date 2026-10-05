import { Component, t, useProps } from "@odoo/owl";

import { ImStatus } from "@mail/core/common/im_status";

/**
 * Wrapper for the discuss ImStatus Component, to be used inside the softphone.
 */
export class VoipImStatus extends Component {
    static components = { ImStatus };
    static template = "voip.VoipImStatus";

    props = useProps({
        // Contrary to ImStatus, we allow giving an undefined persona, which is
        // useful to avoid ifs in the callers that might work with phone numbers
        // alongside partners.
        persona: t.or([t.object(), t.literal(false), t.literal(null)]).optional(),

        // Same as ImStatus
        className: t.string().optional(),
        style: t.string().optional(),
    });
}

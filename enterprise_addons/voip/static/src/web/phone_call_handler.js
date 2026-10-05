import { phoneCallHandlerRegistry } from "@web/core/phone/phone_call";

const pendingCalls = new Set();

phoneCallHandlerRegistry.add("voip", {
    isApplicable(env) {
        return Boolean(env.services.voip);
    },

    async execute(env, params, { fallback }) {
        const voip = env.services.voip;
        const callKey =
            params.activity || `${params.resModel}/${params.resId}/${params.phoneNumber}`;
        if (pendingCalls.has(callKey)) {
            return false;
        }
        pendingCalls.add(callKey);
        try {
            const callMade = await voip.userAgent.makeCall(
                {
                    activity: params.activity,
                    phone_number: params.phoneNumber,
                    res_id: params.resId,
                    res_model: params.resModel,
                },
                {
                    fallback,
                    onUnavailable: fallback,
                }
            );
            return callMade;
        } finally {
            pendingCalls.delete(callKey);
        }
    },
});

declare module "models" {
    export interface Activity {
        requestSignature: (template_id?: number | boolean) => Promise<unknown>;
        openSignRequestForm: () => void;
        resendSignatureAccesses: () => Promise<void>;
        goToSignableDocument: () => Promise<void>;
    }
}

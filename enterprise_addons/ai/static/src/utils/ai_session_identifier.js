import { uuid } from "@web/core/utils/strings";

// Identify this page instance independently of the shared login session.
export const aiSessionIdentifier = uuid();

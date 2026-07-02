import { applyDemoDataset, applyPreviewMock } from "./previewMock/scenarios";
import { DEV_MOCK } from "./previewMock/devMock";

// The preview mock ships with the demo dataset applied, matching the former
// module-initialization side effect of previewMock.js.
applyDemoDataset();

export { DEV_MOCK, applyPreviewMock };

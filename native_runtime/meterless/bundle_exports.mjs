import bridge from "./world_model_bridge.js";
const reference = bridge.loadReference();
export const WorldModel = reference.WorldModel;
export const normalizeName = reference.normalizeName;
export const entityIdFromName = reference.entityIdFromName;
export const decide = reference.decide;

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// v2 MODEL_CALL contract — the JSON envelope exchanged between the kernel
/// and Python. `meta` carries anything in the glyph's params.Map beyond
/// backend/prompt/version.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ModelCallPayload {
    pub backend: String,
    pub prompt: String,
    pub version: String,
    #[serde(default)]
    pub meta: HashMap<String, String>,
}

impl ModelCallPayload {
    pub fn to_json(&self) -> String {
        serde_json::to_string(self).expect("ModelCallPayload always serializes")
    }
}

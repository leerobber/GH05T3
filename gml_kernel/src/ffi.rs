use crate::gh05t3::core_loop::create_gh05t3_agent;
use crate::kernel::{executor::execute_block, payload::ModelCallPayload, KernelState};
use std::collections::HashMap;

#[no_mangle]
pub extern "C" fn gh05t3_run_core_loop() -> *mut std::os::raw::c_char {
    let mut kernel = KernelState::new();
    let mut agent = create_gh05t3_agent();

    let core_loop = agent.core_loop.clone();
    execute_block(&core_loop, &mut agent, &mut kernel);

    let summary = format!(
        "ticks={},short_term={:?}",
        kernel.tick, agent.memory.short_term
    );

    let c_string = std::ffi::CString::new(summary).unwrap();
    c_string.into_raw()
}

/// v2 MODEL_CALL contract: builds the JSON envelope shared by the exported
/// FFI symbol below and by `kernel::executor::model_call` — same crate, so
/// no need to round-trip through the C ABI to call this from within Rust.
pub fn model_call_summary(
    backend: &str,
    prompt: &str,
    version: &str,
    meta: HashMap<String, String>,
) -> String {
    ModelCallPayload {
        backend: backend.to_string(),
        prompt: prompt.to_string(),
        version: version.to_string(),
        meta,
    }
    .to_json()
}

#[no_mangle]
pub extern "C" fn gh05t3_model_call(
    backend_ptr: *const std::os::raw::c_char,
    prompt_ptr: *const std::os::raw::c_char,
    version_ptr: *const std::os::raw::c_char,
) -> *mut std::os::raw::c_char {
    let (backend, prompt, version) = unsafe {
        (
            std::ffi::CStr::from_ptr(backend_ptr).to_string_lossy().into_owned(),
            std::ffi::CStr::from_ptr(prompt_ptr).to_string_lossy().into_owned(),
            std::ffi::CStr::from_ptr(version_ptr).to_string_lossy().into_owned(),
        )
    };

    let summary = model_call_summary(&backend, &prompt, &version, HashMap::new());
    std::ffi::CString::new(summary).unwrap().into_raw()
}

#[no_mangle]
pub extern "C" fn gh05t3_free_string(ptr: *mut std::os::raw::c_char) {
    if ptr.is_null() {
        return;
    }
    unsafe {
        drop(std::ffi::CString::from_raw(ptr));
    }
}

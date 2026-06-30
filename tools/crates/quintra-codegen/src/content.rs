//! Phase-1 stub: empty registry. Phase 2 wires up the real `content/*.rs`
//! files via Rust's module include mechanism (or `include!()`).

use quintra_content::Registry;

pub fn build_registry() -> Registry {
    Registry::new()
}

//! quintra-codegen — emits C tables from `content/*.rs` content registry.
//!
//! Phase-1 stub: validates registry, writes a minimal `content_stubs.h`
//! header so the C build doesn't fail on missing includes.  Phase 2 will
//! flesh out the per-type emitters.

use std::path::PathBuf;

use anyhow::{Context, Result};
use clap::Parser;

mod content;     // hand-authored content tree (will be wired up in Phase 2)
mod emit;

#[derive(Parser, Debug)]
#[command(name = "quintra-codegen")]
struct Args {
    /// Path to project's content/ directory (currently unused — Phase 1)
    #[arg(long, default_value = "../content")]
    content: PathBuf,

    /// Where to write generated C/H files
    #[arg(long, default_value = "../src/generated")]
    out: PathBuf,
}

fn main() -> Result<()> {
    let args = Args::parse();
    std::fs::create_dir_all(&args.out)
        .with_context(|| format!("create out dir {}", args.out.display()))?;

    // Phase 1: validate empty registry, emit stub header.
    let reg = content::build_registry();
    if let Err(errs) = reg.validate() {
        eprintln!("quintra-codegen: content validation FAILED:");
        for e in &errs { eprintln!("  - {e}"); }
        std::process::exit(1);
    }

    emit::write_stub_header(&args.out, &reg)?;

    println!(
        "quintra-codegen: ok ({} classes, {} items, {} enemies, {} biomes, {} rooms)",
        reg.n_classes(), reg.n_items(), reg.n_enemies(), reg.n_biomes(),
        reg.n_room_templates()
    );
    Ok(())
}

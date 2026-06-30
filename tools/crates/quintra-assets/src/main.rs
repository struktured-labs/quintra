//! quintra-assets — PNG → GBC tile/sprite data, palette quantize, music.
//! Phase 1 stub.

use anyhow::Result;
use clap::Parser;
use std::path::PathBuf;

#[derive(Parser, Debug)]
#[command(name = "quintra-assets")]
struct Args {
    #[arg(long, default_value = "../assets")]
    input: PathBuf,
    #[arg(long, default_value = "../src/generated")]
    out:   PathBuf,
}

fn main() -> Result<()> {
    let args = Args::parse();
    std::fs::create_dir_all(&args.out)?;
    println!("quintra-assets: (Phase 1 stub) input={}, out={}",
        args.input.display(), args.out.display());
    Ok(())
}

use std::env;
use std::path::Path;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<String> = env::args().collect();
    if args.len() != 3 {
        eprintln!("Usage: cargo run -p rbxlx -- <input.rbxlx> <output.rbxlx>");
        std::process::exit(1);
    }

    let input = Path::new(&args[1]);
    let output = Path::new(&args[2]);

    rbxlx::sanitize_rbxlx(input, output)?;
    println!("Fixed and saved to {}", output.display());
    Ok(())
}

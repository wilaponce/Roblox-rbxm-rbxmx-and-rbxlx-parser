use std::fs::File;
use std::io::{BufReader, BufWriter};
use std::path::Path;

pub fn sanitize_rbxlx(input: &Path, output: &Path) -> Result<(), Box<dyn std::error::Error>> {
    let reader = BufReader::new(File::open(input)?);
    let dom = rbx_xml::from_reader_default(reader)?;

    let writer = BufWriter::new(File::create(output)?);
    let root_ids = dom.root().children();
    rbx_xml::to_writer_default(writer, &dom, root_ids)?;

    Ok(())
}

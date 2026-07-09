//! GBC tile encoding + C emission.
//!
//! Ported 1:1 from scripts/sprite_authoring.py — output must stay
//! byte-identical (the golden test pins it against the checked-in
//! src/render/sprites_gen.c).

/// Parse ASCII grid lines into rows of palette indices 0..=3.
/// Glyphs: '.' and '0' = 0 (transparent / palette c0), '1'..'3' literal.
pub fn parse_grid(lines: &[&str]) -> Vec<Vec<u8>> {
    lines
        .iter()
        .map(|line| {
            line.chars()
                .map(|c| match c {
                    '.' | '0' => 0,
                    '1' => 1,
                    '2' => 2,
                    '3' => 3,
                    other => panic!("bad glyph {other:?} in grid line {line:?}"),
                })
                .collect()
        })
        .collect()
}

/// One 8x8 indexed tile -> 16 GBDK 2bpp bytes (low plane, high plane per row).
pub fn tile_2bpp_bytes(tile: &[Vec<u8>]) -> Vec<u8> {
    let mut out = Vec::with_capacity(16);
    for row in tile {
        let mut lo: u8 = 0;
        let mut hi: u8 = 0;
        for (x, idx) in row.iter().enumerate() {
            let bit = 7 - x as u8; // MSB = leftmost
            lo |= (idx & 0x1) << bit;
            hi |= ((idx >> 1) & 0x1) << bit;
        }
        out.push(lo);
        out.push(hi);
    }
    out
}

/// Nearest-neighbour 2x upscale (8x8 enemy -> 16x16 mini-boss silhouette).
pub fn scale2x(grid: &[Vec<u8>]) -> Vec<Vec<u8>> {
    let mut out = Vec::with_capacity(grid.len() * 2);
    for row in grid {
        let mut doubled = Vec::with_capacity(row.len() * 2);
        for &px in row {
            doubled.push(px);
            doubled.push(px);
        }
        out.push(doubled.clone());
        out.push(doubled);
    }
    out
}

/// Slice a W x H grid into 8x8 tiles, row-major (TL, TR, BL, BR for 16x16).
pub fn sprite_to_tiles(grid: &[Vec<u8>], w: usize, h: usize) -> Vec<Vec<Vec<u8>>> {
    let mut tiles = Vec::new();
    for ty in (0..h).step_by(8) {
        for tx in (0..w).step_by(8) {
            let tile: Vec<Vec<u8>> = grid[ty..ty + 8]
                .iter()
                .map(|row| row[tx..tx + 8].to_vec())
                .collect();
            tiles.push(tile);
        }
    }
    tiles
}

pub fn emit_tile_c_array(name: &str, tile_bytes: &[u8]) -> String {
    let body = tile_bytes
        .iter()
        .map(|b| format!("0x{b:02X}"))
        .collect::<Vec<_>>()
        .join(", ");
    format!("const u8 {name}[16] = {{ {body} }};")
}

pub fn emit_metasprite_c_array(name: &str, tiles: &[Vec<Vec<u8>>]) -> String {
    let flat: Vec<u8> = tiles.iter().flat_map(|t| tile_2bpp_bytes(t)).collect();
    let body = flat
        .iter()
        .map(|b| format!("0x{b:02X}"))
        .collect::<Vec<_>>()
        .join(", ");
    format!("const u8 {name}[{}] = {{ {body} }};", flat.len())
}

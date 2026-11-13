use std::fmt::Write;
use crate::gbc::{sprite_to_tiles, emit_metasprite_c_array};
type Grid = Vec<Vec<u8>>;

fn dot(g: &mut Grid, x: i32, y: i32, c: u8) {
    if y>=0 && x>=0 && (y as usize)<g.len() && (x as usize)<g[0].len() {
        g[y as usize][x as usize]=c;
    }
}
fn oval(g: &mut Grid, cx: i32, cy: i32, rx: i32, ry: i32, fill: u8) {
    let inner_rx = (rx - 1).max(1);
    let inner_ry = (ry - 1).max(1);
    for y in cy-ry..=cy+ry { for x in cx-rx..=cx+rx {
        let d=(x-cx)*(x-cx)*ry*ry+(y-cy)*(y-cy)*rx*rx;
        if d<=rx*rx*ry*ry {
            // Diagonal rim light. A vertical cut at x<cx left a hard seam.
            let rim = d > inner_rx*inner_rx*inner_ry*inner_ry;
            let lit = (x - cx) + (y - cy) < -(rx / 3).max(1);
            let c = if rim { 1 } else if lit { 3 } else { fill };
            dot(g,x,y,c);
        }
    }}
}
fn stroke(g: &mut Grid, points: &[(i32,i32)], width: i32) {
    for p in points.windows(2) {
        let (x0,y0)=p[0]; let (x1,y1)=p[1];
        let n=(x1-x0).abs().max((y1-y0).abs()).max(1);
        for k in 0..=n {
            let x=x0+(x1-x0)*k/n; let y=y0+(y1-y0)*k/n;
            for dy in -width..=width { for dx in -width..=width {
                dot(g,x+dx,y+dy,if dx==-width || dy==width {1} else if dy<0 {3} else {2});
            }}
        }
    }
}
pub fn crystal() -> Grid { crystal_pose(false) }

/// Levitating refraction pose. Fists rise, the legs pull up, and the
/// torso highlights swap so the second frame is obvious at native scale.
pub fn crystal_refract() -> Grid { crystal_pose(true) }

fn crystal_pose(refract: bool) -> Grid {
    // GPT Image 2.6 Sunburst pass (2026-11-13), hand-quantized to 32x32:
    // lit crown facets, a visor with a toothed grin, diagonally faceted
    // fists, an outlined chest gem and ivory-capped feet.
    let mut g=vec![vec![0;32];32];
    for &(cx,top,bottom,w) in &[(16,0,10,4),(7,5,13,3),(25,3,13,3)] {
        for y in top..bottom {let r=(y-top).min(w); for x in cx-r..=cx+r {
            let lit = x<cx || (x==cx && y-top<w);
            dot(&mut g,x,y,if x==cx-r || x==cx+r {1}else if lit {3}else{2});
        }}
    }
    for y in 11..27 {let inset=if y<14 {14-y}else if y>22 {y-22}else{0};
        for x in 8+inset..=24-inset {
            let lit = x<12 || (x<14 && y<16);
            dot(&mut g,x,y,if x==8+inset || x==24-inset {1}else if lit {3}else{2});
        }
    }
    let fist_top = if refract { 11 } else { 13 };
    let fist_bot = if refract { 23 } else { 25 };
    for &(left,right) in &[(1,8),(24,31)] {for y in fist_top..fist_bot {for x in left..right {
        let edge=x==left || x==right-1 || y==fist_bot-1;
        // One diagonal facet splits the lit outer-top plane from the block.
        let facet=(if left==1 {x-left} else {right-1-x})+(y-fist_top);
        dot(&mut g,x,y,if edge {1}else if facet<6 {3}else if facet==6 {1}else{2});
    }}}
    for y in 8..17 {for x in 9..24 {dot(&mut g,x,y,if y==8 || x==9 || x==23 {1}else if y==9 {3}else{2});}}
    for y in 11..14 {for x in 11..22 {dot(&mut g,x,y,1);}}
    for &(x,y) in &[(11,12),(12,12),(13,13),(21,12),(20,12),(19,13)] {dot(&mut g,x,y,3);}
    for x in 13..20 {dot(&mut g,x,15,1);}
    for x in 13..20 {dot(&mut g,x,16,if (x-13)%2==0 {3}else{1});}
    for y in 18i32..25 {let r=3-(y-21).abs(); for x in 16-r..=16+r {
        dot(&mut g,x,y,if (x-16).abs()==r {1}else if y<21 || (y==21 && x<16) {3}else{2});
    }}
    let leg_top = if refract { 29 } else { 27 };
    for &(left,right) in &[(7,14),(19,26)] {for y in leg_top..32 {for x in left..right {
        dot(&mut g,x,y,if y==31 || x==right-1 || x==left {1}else if y==leg_top || x<left+3 {3}else{2});
    }}}
    if refract {
        for y in 14..22 { for x in 12..20 {
            g[y][x] = match g[y][x] { 2 => 3, 3 => 2, other => other };
        }}
    }
    g
}
fn spider_pose(crouch: bool) -> Grid {
    let mut g=vec![vec![0;48];32];
    let dip = if crouch { 1 } else { 0 };
    let flex = if crouch { 2 } else { 0 };
    for side in [-1i32,1] {
        let paths = [
            vec![(8,12+dip),(15-flex,3),(21,1)],
            vec![(9,15+dip),(20+flex,8),(23,12)],
            vec![(9,19+dip),(20-flex,21),(23,27)],
            vec![(7,22+dip),(15+flex,29),(19,31)],
        ];
        for path in paths {
            let p:Vec<_>=path.iter().map(|&(x,y)|(24+side*x,y)).collect();
            stroke(&mut g,&p,1);
        }
    }
    oval(&mut g,24,11+dip,10,9,2);
    oval(&mut g,24,21+dip,8,7,2);
    for y in 5..12 { for x in 21..=26 {dot(&mut g,x,y+dip,if (x+y)%5==0 {3}else{2});}}
    let mouth = if crouch { 2 } else { 0 };
    for x in 18..=30 { dot(&mut g,x,20+dip,1); dot(&mut g,x,21+dip,1); }
    for &(x,y) in &[(19,20),(20,20),(27,20),(28,20)] {
        dot(&mut g, x + if x<24 { -mouth } else { mouth }, y+dip, 3);
    }
    for y in 24..30 { dot(&mut g,21+(y-24)/3,y,3); dot(&mut g,27-(y-24)/3,y,3); }
    g
}
fn spider() -> Grid { spider_pose(false) }
fn mire_pose(contract: bool) -> Grid {
    let mut g=vec![vec![0;32];48];
    let pull = if contract { 2 } else { 0 };
    let lift = if contract { 2 } else { 0 };
    let roots = [
        vec![(12,19),(5+pull,13),(3+pull,3),(8,1)],
        vec![(22,19),(29-pull,12),(27-pull,3),(24,5)],
        vec![(11,32),(4+pull,37-lift),(2+pull,45-lift),(9,46-lift)],
        vec![(22,31),(28-pull,37-lift),(29-pull,45-lift),(23,47-lift)],
    ];
    for p in roots { stroke(&mut g,&p,1); }
    stroke(&mut g,&[(11-pull,12),(10-pull,5),(14,2)],1);
    stroke(&mut g,&[(23+pull,13),(23+pull,6),(20,2)],1);
    let widths: [i32;24]=[6,9,11,12,13,13,13,13,13,13,12,12,11,11,10,9,8,7,6,5,4,3,2,1];
    for (row,&half) in widths.iter().enumerate() {
        let y=12+row as i32;
        let w=half-if contract {2}else{0};
        if w<1 {continue;}
        for x in 16-w..=16+w {
            if row<5 && (x-16).abs()<5-row as i32 {continue;}
            let edge=(x-16).abs()==w || row==0;
            // A short upper-left curve, not the old flat slab at x<13.
            let highlight = x < 16 && (16 - x) + (y - 18) < 8 && (x + y) % 2 == 0;
            let valve = contract && (x-16).abs() <= 1 && row > 6 && row < 12;
            dot(&mut g,x,y+if contract {1}else{0},if valve {3}else if edge {1}else if highlight {3}else{2});
        }
    }
    // A narrow branching vein leaves both lobes and the pointed silhouette intact.
    stroke(&mut g,&[(17,19),(15,24),(18,28),(17,32)],0);
    stroke(&mut g,&[(15,24),(10,26)],0);
    for &(x,y) in &[(10,20),(11,20),(12,21),(21,20),(22,20),(20,21)] {
        dot(&mut g,x,y+if contract {1}else{0},1);
    }
    g
}
fn mire() -> Grid { mire_pose(false) }
fn hydra_pose(strike: bool) -> Grid {
    let mut g=vec![vec![0;48];32];
    oval(&mut g,24,25,16,6,2);
    // Wrapped rib scales instead of an 8px striped rectangle and a black void.
    for k in 0..5 {
        let y = 22 + k;
        let half = 12 - k;
        for x in (24-half)..=(24+half) {
            if (x + k) % 3 == 0 { dot(&mut g, x, y, if x < 24 { 3 } else { 1 }); }
        }
    }
    let heads: [(i32,i32,i32);3] = if strike {
        [(13,5,10),(24,24,8),(35,43,11)]
    } else {
        [(15,7,8),(24,24,4),(33,41,9)]
    };
    for (n,&(root,head,hy)) in heads.iter().enumerate() {
        let lean = match n { 0 => -2, 2 => 2, _ => 0 };
        stroke(&mut g,&[(root,25),(root+lean,18),(head,hy+6)],2);
        oval(&mut g,head,hy,6,5,2);
        let jaw = if strike { 3 } else { 0 };
        for x in head-4..=head+4 { dot(&mut g,x,hy+1+jaw,1); }
        if strike {
            for x in head-3..=head+3 { if x != head { dot(&mut g,x,hy+2,3); } }
            dot(&mut g,head,hy+3,3);
        }
        for x in [head-3,head+3] { dot(&mut g,x,hy-1,3); }
        for k in 0..4 { dot(&mut g,head-4-k/2,hy-3-k,3); dot(&mut g,head+4+k/2,hy-3-k,2); }
    }
    let step = if strike { 1 } else { 0 };
    for (i,x) in [11,16,32,37].iter().enumerate() {
        let x = x + if i % 2 == 0 { step } else { -step };
        for y in 28..32 { dot(&mut g,x,y,3); dot(&mut g,x+1,y,1); }
    }
    g
}
fn hydra() -> Grid { hydra_pose(false) }

pub fn generate() -> String {
    let mut out=String::from("// Generated by quintra-assets.\n#pragma bank 13\n#include <gb/gb.h>\n#include <gb/cgb.h>\n#include \"core/types.h\"\n");
    for (name,g) in [("spider",spider()),("mire",mire()),("hydra",hydra()),("mire_contract",mire_pose(true))] {
        let tiles=sprite_to_tiles(&g,g[0].len(),g.len());
        assert_eq!(tiles.len(),24);
        writeln!(out,"{}",emit_metasprite_c_array(&format!("large_{name}"),&tiles)).unwrap();
    }
    out.push_str("void large_boss_pose_b_load(u8 stage) BANKED;\nvoid large_boss_load(u8 stage) BANKED {\n    VBK_REG=1;\n    set_sprite_data(40,24,stage==3 ? large_spider : stage==4 ? large_mire : large_hydra);\n    if(stage==4) set_sprite_data(64,24,large_mire_contract);\n    VBK_REG=0;\n    if(stage==3 || stage==7) large_boss_pose_b_load(stage);\n}\n");
    out
}

pub fn generate_crystal_pose() -> String {
    let tiles = sprite_to_tiles(&crystal_refract(), 32, 32);
    assert_eq!(tiles.len(), 16);
    let mut out = String::from("// Generated by quintra-assets.\n#pragma bank 12\n#include <gb/gb.h>\n#include <gb/cgb.h>\n#include \"core/types.h\"\n");
    writeln!(out, "{}", emit_metasprite_c_array("crystal_refract", &tiles)).unwrap();
    out.push_str("void crystal_pose_b_load(void) BANKED {\n    VBK_REG=1;\n    set_sprite_data(128,16,crystal_refract);\n    VBK_REG=0;\n}\n");
    out
}

/// Crouch and strike poses live outside bank 13. That bank has only a few
/// hundred bytes under the layout floor, and each pose is 384 bytes.
pub fn generate_pose_b() -> String {
    let mut out=String::from("// Generated by quintra-assets.\n// Fixed bank: autobank packed these 768 bytes of pose tiles into _CODE_2.\n#pragma bank 14\n#include <gb/gb.h>\n#include <gb/cgb.h>\n#include \"core/types.h\"\n");
    for (name,g) in [("spider_crouch",spider_pose(true)),("hydra_strike",hydra_pose(true))] {
        let tiles=sprite_to_tiles(&g,g[0].len(),g.len());
        assert_eq!(tiles.len(),24);
        writeln!(out,"{}",emit_metasprite_c_array(&format!("large_{name}"),&tiles)).unwrap();
    }
    out.push_str("void large_boss_pose_b_load(u8 stage) BANKED {\n    VBK_REG=1;\n    set_sprite_data(64,24,stage==3 ? large_spider_crouch : large_hydra_strike);\n    VBK_REG=0;\n}\n");
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn mire_pulse_flexes_roots_and_contracts_heart() {
        let open=mire_pose(false);
        let shut=mire_pose(true);
        let differ=|a: &[Vec<u8>], b: &[Vec<u8>]| {
            a.iter().flatten().zip(b.iter().flatten()).filter(|(p,q)| p!=q).count()
        };
        assert!(differ(&open[..12], &shut[..12]) >= 8, "upper roots stayed rigid");
        assert!(differ(&open[37..], &shut[37..]) >= 8, "lower roots stayed rigid");
        let mass=|g: &Grid| g[12..37].iter().flatten().filter(|&&p|p!=0).count();
        assert!(mass(&open)>mass(&shut)+40);
        assert_eq!(open[13][16],0);
        assert_eq!(open[35][16],2);
        // The old left lobe was a solid yellow slab. A thin curve is allowed.
        let slab=open.iter().take(25).flat_map(|row| row.iter().take(13)).filter(|&&p|p==3).count();
        assert!(slab < 40, "left lobe is still a flat slab ({slab})");
    }
    #[test]
    fn spider_and_hydra_have_a_second_pose() {
        let changed=|a: &Grid, b: &Grid| a.iter().flatten().zip(b.iter().flatten()).filter(|(p,q)| p!=q).count();
        assert!(changed(&spider(), &spider_pose(true)) > 40);
        assert!(changed(&hydra(), &hydra_pose(true)) > 40);
        assert_ne!(spider()[20][24], 0);
        let idle = crystal();
        let bent = crystal_refract();
        assert!(changed(&idle, &bent) > 40, "crystal refraction matches the idle pose");
        assert_eq!(idle, crystal_pose(false));
    }
    #[test]
    fn enlarged_bosses_have_distinct_native_bodies() {
        let bodies=[spider(),mire(),hydra()];
        for (i,g) in bodies.iter().enumerate() {
            assert_eq!(g.len()*g[0].len(),1536);
            assert!(g.iter().flatten().all(|&p|p<4));
            assert!(g.iter().flatten().filter(|&&p|p>0).count()>400);
            assert!(g.iter().flatten().filter(|&&p|p==3).count()>100);
            for other in &bodies[..i] {assert_ne!(g,other);}
        }
    }
    #[test]
    fn generated_large_atlas_matches_source() {
        let root=concat!(env!("CARGO_MANIFEST_DIR"),"/../../..");
        assert_eq!(generate(),std::fs::read_to_string(format!("{root}/src/render/large_boss_gen.c")).unwrap());
        assert_eq!(generate_pose_b(),std::fs::read_to_string(format!("{root}/src/render/large_boss_pose_b.c")).unwrap());
        assert_eq!(generate_crystal_pose(),std::fs::read_to_string(format!("{root}/src/render/crystal_pose_b.c")).unwrap());
    }
}

use std::fmt::Write;
use crate::gbc::{sprite_to_tiles, emit_metasprite_c_array};
type Grid = Vec<Vec<u8>>;

fn dot(g: &mut Grid, x: i32, y: i32, c: u8) {
    if y>=0 && x>=0 && (y as usize)<g.len() && (x as usize)<g[0].len() {
        g[y as usize][x as usize]=c;
    }
}
fn oval(g: &mut Grid, cx: i32, cy: i32, rx: i32, ry: i32, fill: u8) {
    for y in cy-ry..=cy+ry { for x in cx-rx..=cx+rx {
        let d=(x-cx)*(x-cx)*ry*ry+(y-cy)*(y-cy)*rx*rx;
        if d<=rx*rx*ry*ry {
            let c=if d>(rx-1)*(rx-1)*(ry-1)*(ry-1) {1}
                else if x<cx-1 && y<cy+ry/3 {3} else {fill};
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
pub fn crystal() -> Grid {
    let mut g=vec![vec![0;32];32];
    for &(cx,top,bottom,w) in &[(16,0,10,4),(7,5,13,3),(25,3,13,3)] {
        for y in top..bottom {let r=(y-top).min(w); for x in cx-r..=cx+r {
            dot(&mut g,x,y,if x==cx-r || x==cx+r {1}else if x<=cx {3}else{2});
        }}
    }
    for y in 11..27 {let inset=if y<14 {14-y}else if y>22 {y-22}else{0};
        for x in 8+inset..=24-inset {dot(&mut g,x,y,if x==8+inset || x==24-inset {1}else if x<16 {3}else{2});}
    }
    for &(left,right) in &[(1,8),(24,31)] {for y in 13..25 {for x in left..right {
        let edge=x==left || x==right-1 || y==24;
        dot(&mut g,x,y,if edge {1}else if y<18 || x==left+1 {3}else{2});
    }}}
    for y in 8..17 {for x in 9..24 {dot(&mut g,x,y,if y==8 || x==9 || x==23 {1}else{2});}}
    for y in 11..14 {for x in 11..22 {dot(&mut g,x,y,1);}}
    for &(x,y) in &[(11,12),(12,12),(13,13),(21,12),(20,12),(19,13)] {dot(&mut g,x,y,3);}
    for x in 13..20 {dot(&mut g,x,16,1);}
    dot(&mut g,14,17,3); dot(&mut g,18,17,3);
    for y in 19i32..24 {let r=2-(y-21).abs(); for x in 16-r..=16+r {dot(&mut g,x,y,if x<=16 {3}else{1});}}
    for &(left,right) in &[(7,14),(19,26)] {for y in 27..32 {for x in left..right {
        dot(&mut g,x,y,if y==31 || x==right-1 {1}else if x<left+4 {3}else{2});
    }}}
    g
}
fn spider() -> Grid {
    let mut g=vec![vec![0;48];32];
    for side in [-1,1] {
        for path in [vec![(8,12),(15,3),(21,1)], vec![(9,15),(20,8),(23,12)],
                     vec![(9,19),(20,21),(23,27)],vec![(7,22),(15,29),(19,31)]] {
            let p:Vec<_>=path.iter().map(|&(x,y)|(24+side*x,y)).collect();
            stroke(&mut g,&p,1);
        }
    }
    oval(&mut g,24,11,10,9,2);
    oval(&mut g,24,21,8,7,2);
    // Broad ice plates above an unmistakable dark face and paired fangs.
    for y in 5..12 { for x in 21..=26 {dot(&mut g,x,y,if x<24 {3}else{2});}}
    for x in 18..=30 { dot(&mut g,x,20,1); dot(&mut g,x,21,1); }
    for &(x,y) in &[(19,20),(20,20),(27,20),(28,20),(21,17),(27,17)] { dot(&mut g,x,y,3); }
    for y in 24..30 { dot(&mut g,21+(y-24)/3,y,3); dot(&mut g,27-(y-24)/3,y,3); }
    g
}
fn mire_pose(contract: bool) -> Grid {
    let mut g=vec![vec![0;32];48];
    for p in [vec![(12,19),(5,13),(3,3),(8,1)], vec![(22,19),(29,12),(27,3),(24,5)],
              vec![(11,32),(4,37),(2,45),(9,46)],vec![(22,31),(28,37),(29,45),(23,47)]] {
        stroke(&mut g,&p,1);
    }
    stroke(&mut g,&[(11,12),(10,5),(14,2)],1);
    stroke(&mut g,&[(23,13),(23,6),(20,2)],1);
    let widths: [i32;24]=[6,9,11,12,13,13,13,13,13,13,12,12,11,11,10,9,8,7,6,5,4,3,2,1];
    for (row,&half) in widths.iter().enumerate() {
        let y=12+row as i32;
        let w=half-if contract {2}else{0};
        if w<1 {continue;}
        for x in 16-w..=16+w {
            if row<5 && (x-16).abs()<5-row as i32 {continue;}
            let edge=(x-16).abs()==w || row==0;
            let highlight=x<13 && y<25 && x>16-w+2;
            dot(&mut g,x,y+if contract {1}else{0},if edge {1}else if highlight {3}else{2});
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
fn hydra() -> Grid {
    let mut g=vec![vec![0;48];32];
    oval(&mut g,24,25,16,6,2);
    for &(root,head,hy) in &[(15,7,8),(24,24,5),(33,40,9)] {
        stroke(&mut g,&[(root,25),(root,18),(head,hy+6)],2);
        oval(&mut g,head,hy,6,5,2);
        for x in head-4..=head+4 {dot(&mut g,x,hy+1,1);}
        for x in [head-3,head+3] {dot(&mut g,x,hy-1,3);dot(&mut g,x,hy+2,3);}
        for k in 0..4 {dot(&mut g,head-4-k/2,hy-3-k,3);dot(&mut g,head+4+k/2,hy-3-k,2);}
    }
    for y in 24..30 {for x in 20..=27 {dot(&mut g,x,y,if y%3==0 {1}else{3});}}
    for x in [11,16,32,37] {for y in 28..32 {dot(&mut g,x,y,3);dot(&mut g,x+1,y,1);}}
    g
}

pub fn generate() -> String {
    let mut out=String::from("// Generated by quintra-assets.\n#pragma bank 13\n#include <gb/gb.h>\n#include <gb/cgb.h>\n#include \"core/types.h\"\n");
    for (name,g) in [("spider",spider()),("mire",mire()),("hydra",hydra()),("mire_contract",mire_pose(true))] {
        let tiles=sprite_to_tiles(&g,g[0].len(),g.len());
        assert_eq!(tiles.len(),24);
        writeln!(out,"{}",emit_metasprite_c_array(&format!("large_{name}"),&tiles)).unwrap();
    }
    out.push_str("void large_boss_load(u8 stage) BANKED {\n    VBK_REG=1;\n    set_sprite_data(40,24,stage==3 ? large_spider : stage==4 ? large_mire : large_hydra);\n    if(stage==4) set_sprite_data(64,24,large_mire_contract);\n    VBK_REG=0;\n}\n");
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn mire_pulse_keeps_roots_and_contracts_heart() {
        let open=mire_pose(false);
        let shut=mire_pose(true);
        assert_eq!(&open[..12], &shut[..12]);
        assert_eq!(&open[37..], &shut[37..]);
        let mass=|g: &Grid| g[12..37].iter().flatten().filter(|&&p|p!=0).count();
        assert!(mass(&open)>mass(&shut)+50);
        assert_eq!(open[13][16],0);
        assert_eq!(open[35][16],2);
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
    }
}

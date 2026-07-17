//! Typed reports for Quintra's controller-only mGBA instrumentation.

use std::{collections::HashMap, fs, path::PathBuf};

use anyhow::{bail, Context, Result};
use clap::{Parser, Subcommand};

const CLASS_NAMES: [&str; 5] = ["Wolfkin", "Sauran", "Corvin", "Picsean", "Vespine"];

#[derive(Debug, Parser)]
#[command(about = "Analyze Quintra mGBA instrumentation")]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Debug, Subcommand)]
enum Command {
    /// Summarize and gate a controller-only balance CSV.
    Report {
        csv: PathBuf,
        #[arg(long)]
        runs: usize,
        #[arg(long)]
        classes: usize,
        #[arg(long, default_value_t = 0)]
        min_wins: usize,
        /// Minimum runs per class that must reach a stocked shop.
        #[arg(long, default_value_t = 0)]
        min_shop_runs: usize,
        /// Per-room frame count above which a live run is classified stalled.
        #[arg(long, default_value_t = 3600)]
        stall_frames: u32,
        /// Maximum allowed live-enemy room stalls across the complete matrix.
        #[arg(long)]
        max_combat_stalls: Option<usize>,
        /// Maximum allowed cleared-room route stalls across the complete matrix.
        #[arg(long)]
        max_route_stalls: Option<usize>,
        /// Maximum authored overworld transitions in any one run.
        #[arg(long)]
        max_world_hops: Option<u32>,
        /// Enemy content ID that must appear in at least one live ROM run.
        #[arg(long = "require-enemy")]
        required_enemies: Vec<u8>,
    },
}

#[derive(Clone, Debug)]
struct Row {
    run: u32,
    seed: u32,
    class: usize,
    max_room: u32,
    rooms_cleared: u32,
    kills: u32,
    bosses: u32,
    min_hp: u32,
    max_combat_frames: u32,
    max_route_frames: u32,
    towns: u32,
    victory: u32,
    ui_screen: u32,
    dodges: u32,
    shop_visits: u32,
    purchases: u32,
    world_hops: u32,
    death_source: u32,
    enemy_mask: u32,
}

fn field<'a>(record: &'a [&str], columns: &HashMap<&str, usize>, name: &str) -> Result<&'a str> {
    let index = columns
        .get(name)
        .with_context(|| format!("balance CSV is missing column {name}"))?;
    record
        .get(*index)
        .copied()
        .with_context(|| format!("balance CSV row is missing value for {name}"))
}

fn number(record: &[&str], columns: &HashMap<&str, usize>, name: &str) -> Result<u32> {
    field(record, columns, name)?
        .parse()
        .with_context(|| format!("balance CSV has non-numeric {name}"))
}

fn parse_rows(text: &str) -> Result<Vec<Row>> {
    let mut lines = text.lines();
    let header = lines.next().context("balance CSV is empty")?;
    let names: Vec<_> = header.split(',').collect();
    let columns: HashMap<_, _> = names.iter().enumerate().map(|(i, name)| (*name, i)).collect();
    let mut rows = Vec::new();
    for (line_index, line) in lines.enumerate() {
        if line.trim().is_empty() {
            continue;
        }
        let record: Vec<_> = line.split(',').collect();
        let row = (|| -> Result<Row> {
            let hostiles = number(&record, &columns, "hostiles")?;
            let has_run_maxima = columns.contains_key("max_combat_frames");
            let final_room_frames = number(&record, &columns, "room_frames")?;
            Ok(Row {
                run: columns
                    .contains_key("run")
                    .then(|| number(&record, &columns, "run"))
                    .transpose()?
                    .unwrap_or(0),
                seed: columns
                    .contains_key("seed")
                    .then(|| number(&record, &columns, "seed"))
                    .transpose()?
                    .unwrap_or(0),
                class: number(&record, &columns, "class")? as usize,
                max_room: number(&record, &columns, "max_room")?,
                rooms_cleared: number(&record, &columns, "rooms_cleared")?,
                kills: number(&record, &columns, "kills")?,
                bosses: number(&record, &columns, "bosses")?,
                min_hp: number(&record, &columns, "min_hp")?,
                // Old reports only retained the final room's dwell. Preserve
                // their old end-state classification for historical summaries.
                max_combat_frames: if has_run_maxima {
                    number(&record, &columns, "max_combat_frames")?
                } else if hostiles > 0 {
                    final_room_frames
                } else {
                    0
                },
                max_route_frames: if has_run_maxima {
                    number(&record, &columns, "max_route_frames")?
                } else if hostiles == 0 {
                    final_room_frames
                } else {
                    0
                },
                towns: number(&record, &columns, "towns")?,
                victory: number(&record, &columns, "victory")?,
                ui_screen: number(&record, &columns, "ui_screen")?,
                dodges: number(&record, &columns, "dodges")?,
                shop_visits: columns
                    .contains_key("shop_visits")
                    .then(|| number(&record, &columns, "shop_visits"))
                    .transpose()?
                    .unwrap_or(0),
                purchases: columns
                    .contains_key("purchases")
                    .then(|| number(&record, &columns, "purchases"))
                    .transpose()?
                    .unwrap_or(0),
                world_hops: columns
                    .contains_key("world_hops")
                    .then(|| number(&record, &columns, "world_hops"))
                    .transpose()?
                    .unwrap_or(0),
                death_source: columns
                    .contains_key("death_source")
                    .then(|| number(&record, &columns, "death_source"))
                    .transpose()?
                    .unwrap_or(255),
                enemy_mask: columns
                    .contains_key("enemy_mask")
                    .then(|| number(&record, &columns, "enemy_mask"))
                    .transpose()?
                    .unwrap_or(0),
            })
        })()
        .with_context(|| format!("invalid balance CSV row {}", line_index + 2))?;
        rows.push(row);
    }
    Ok(rows)
}

fn median(values: impl Iterator<Item = u32>) -> String {
    let mut values: Vec<_> = values.collect();
    values.sort_unstable();
    let middle = values.len() / 2;
    if values.len() % 2 == 1 {
        return values[middle].to_string();
    }
    let sum = values[middle - 1] + values[middle];
    if sum % 2 == 0 {
        (sum / 2).to_string()
    } else {
        format!("{}.5", sum / 2)
    }
}

fn report(
    csv: PathBuf,
    runs: usize,
    classes: usize,
    min_wins: usize,
    min_shop_runs: usize,
    stall_frames: u32,
    max_combat_stalls: Option<usize>,
    max_route_stalls: Option<usize>,
    max_world_hops: Option<u32>,
    required_enemies: Vec<u8>,
) -> Result<()> {
    let text = fs::read_to_string(&csv)
        .with_context(|| format!("failed to read {}", csv.display()))?;
    let rows = parse_rows(&text)?;
    let expected = runs * classes;
    println!("[balance] {}/{} agents reported", rows.len(), expected);

    let mut failures = Vec::new();
    if rows.iter().any(|row| row.run != 0 || row.seed != 0) {
        let mut seeds_by_run: HashMap<u32, u32> = HashMap::new();
        for row in &rows {
            if let Some(seed) = seeds_by_run.insert(row.run, row.seed) {
                if seed != row.seed {
                    failures.push(format!(
                        "run {} is not seed-paired across classes: {} != {}",
                        row.run, seed, row.seed
                    ));
                    break;
                }
            }
        }
        if failures.is_empty() {
            println!("[balance] paired seeds verified across all classes");
        }
    }
    let mut total_combat_stalls = 0;
    let mut total_route_stalls = 0;
    let enemy_mask = rows.iter().fold(0, |mask, row| mask | row.enemy_mask);
    if enemy_mask != 0 {
        let ids = (0..31)
            .filter(|id| enemy_mask & (1 << id) != 0)
            .map(|id| id.to_string())
            .collect::<Vec<_>>()
            .join("|");
        println!("[balance] encountered enemy ids={ids}");
    }
    for (class, name) in CLASS_NAMES.iter().enumerate() {
        let sample: Vec<_> = rows.iter().filter(|row| row.class == class).collect();
        if sample.is_empty() {
            continue;
        }
        let wins = sample.iter().filter(|row| row.victory != 0).count();
        let endings = sample
            .iter()
            .filter(|row| row.victory != 0 && row.ui_screen == 12)
            .count();
        let deaths = sample.iter().filter(|row| row.min_hp == 0).count();
        let death_sources = {
            let values: Vec<_> = sample
                .iter()
                .filter(|row| row.min_hp == 0)
                .map(|row| row.death_source.to_string())
                .collect();
            if values.is_empty() { "-".to_string() } else { values.join("|") }
        };
        let shop_runs = sample.iter().filter(|row| row.shop_visits > 0).count();
        let boss_clears = sample.iter().filter(|row| row.bosses > 0).count();
        let combat_stalls = sample
            .iter()
            .filter(|row| row.max_combat_frames > stall_frames && row.min_hp > 0)
            .count();
        let route_stalls = sample
            .iter()
            .filter(|row| row.max_route_frames > stall_frames && row.min_hp > 0)
            .count();
        total_combat_stalls += combat_stalls;
        total_route_stalls += route_stalls;
        println!(
            "[balance] {name:7} n={} room_med={} clear_med={} kill_med={} boss_med={} \
             boss1={boss_clears}/{} town_med={} shop_med={} buy_med={} shoppers={shop_runs}/{} dodge_med={} wins={wins} endings={endings} \
             deaths={deaths} death_src={death_sources} combat_stalls={combat_stalls} route_stalls={route_stalls}",
            sample.len(),
            median(sample.iter().map(|row| row.max_room)),
            median(sample.iter().map(|row| row.rooms_cleared)),
            median(sample.iter().map(|row| row.kills)),
            median(sample.iter().map(|row| row.bosses)),
            sample.len(),
            median(sample.iter().map(|row| row.towns)),
            median(sample.iter().map(|row| row.shop_visits)),
            median(sample.iter().map(|row| row.purchases)),
            sample.len(),
            median(sample.iter().map(|row| row.dodges)),
        );
        if wins < min_wins {
            failures.push(format!("{name} wins {wins}/{} < required {min_wins}", sample.len()));
        }
        if shop_runs < min_shop_runs {
            failures.push(format!(
                "{name} shop runs {shop_runs}/{} < required {min_shop_runs}", sample.len()
            ));
        }
    }

    if rows.len() != expected {
        bail!("expected {expected} agent reports, found {}", rows.len());
    }
    if let Some(maximum) = max_combat_stalls {
        if total_combat_stalls > maximum {
            failures.push(format!(
                "combat stalls {total_combat_stalls} > allowed {maximum}"
            ));
        }
    }
    if let Some(maximum) = max_route_stalls {
        if total_route_stalls > maximum {
            failures.push(format!(
                "route stalls {total_route_stalls} > allowed {maximum}"
            ));
        }
    }
    if let Some(maximum) = max_world_hops {
        for row in &rows {
            if row.world_hops > maximum {
                failures.push(format!(
                    "class {} run {} overworld hops {} > allowed {}",
                    CLASS_NAMES.get(row.class).unwrap_or(&"unknown"),
                    row.run,
                    row.world_hops,
                    maximum
                ));
            }
        }
    }
    for enemy in required_enemies {
        if enemy >= 31 || enemy_mask & (1u32 << enemy) == 0 {
            failures.push(format!("required enemy {enemy} was never encountered"));
        }
    }
    if !failures.is_empty() {
        bail!("endurance gate FAILED: {}", failures.join("; "));
    }
    println!("[balance] raw data: {}", csv.display());
    Ok(())
}

fn main() -> Result<()> {
    match Cli::parse().command {
        Command::Report {
            csv,
            runs,
            classes,
            min_wins,
            min_shop_runs,
            stall_frames,
            max_combat_stalls,
            max_route_stalls,
            max_world_hops,
            required_enemies,
        } => report(
            csv,
            runs,
            classes,
            min_wins,
            min_shop_runs,
            stall_frames,
            max_combat_stalls,
            max_route_stalls,
            max_world_hops,
            required_enemies,
        ),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn median_formats_whole_and_half_values() {
        assert_eq!(median([3, 1, 2].into_iter()), "2");
        assert_eq!(median([4, 2].into_iter()), "3");
        assert_eq!(median([1, 2].into_iter()), "1.5");
    }

    #[test]
    fn parser_uses_headers_instead_of_fixed_column_positions() {
        let csv = "class,victory,ui_screen,min_hp,max_room,rooms_cleared,kills,bosses,room_frames,hostiles,towns,dodges\n\
                   2,1,12,3,54,31,149,9,120,0,2,89\n";
        let rows = parse_rows(csv).unwrap();
        assert_eq!(rows.len(), 1);
        assert_eq!(rows[0].class, 2);
        assert_eq!(rows[0].bosses, 9);
        assert_eq!(rows[0].dodges, 89);
        assert_eq!(rows[0].purchases, 0, "historical reports default purchases");
        assert_eq!(rows[0].death_source, 255, "historical reports default cause");
        assert_eq!(rows[0].enemy_mask, 0, "historical reports default coverage");
    }

    #[test]
    fn parser_tracks_controller_only_shop_purchases() {
        let csv = "class,victory,ui_screen,min_hp,max_room,rooms_cleared,kills,bosses,room_frames,hostiles,towns,dodges,purchases\n\
                   4,1,12,2,54,30,121,9,90,0,2,77,3\n";
        let rows = parse_rows(csv).unwrap();
        assert_eq!(rows[0].purchases, 3);
    }

    #[test]
    fn parser_tracks_procedural_enemy_coverage() {
        let csv = "class,victory,ui_screen,min_hp,max_room,rooms_cleared,kills,bosses,room_frames,hostiles,towns,dodges,enemy_mask\n\
                   4,1,12,2,54,30,121,9,90,0,2,77,262147\n";
        let rows = parse_rows(csv).unwrap();
        assert_eq!(rows[0].enemy_mask, (1 << 18) | (1 << 1) | 1);
    }

    #[test]
    fn parser_tracks_runtime_death_source() {
        let csv = "class,victory,ui_screen,min_hp,max_room,rooms_cleared,kills,bosses,room_frames,hostiles,towns,dodges,death_source\n\
                   3,0,11,0,43,21,92,7,166,0,2,42,7\n";
        let rows = parse_rows(csv).unwrap();
        assert_eq!(rows[0].death_source, 7);
    }

    #[test]
    fn parser_retains_worst_room_dwell_from_successful_runs() {
        let csv = "class,victory,ui_screen,min_hp,max_room,rooms_cleared,kills,bosses,room_frames,max_combat_frames,max_route_frames,hostiles,towns,dodges\n\
                   1,1,12,9,54,26,115,9,214,19000,700,0,2,87\n";
        let rows = parse_rows(csv).unwrap();
        assert_eq!(rows[0].max_combat_frames, 19_000);
        assert_eq!(rows[0].max_route_frames, 700);
        assert!(rows[0].victory != 0, "fixture must prove a successful run");
    }
}

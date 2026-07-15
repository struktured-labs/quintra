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
    },
}

#[derive(Clone, Debug)]
struct Row {
    class: usize,
    max_room: u32,
    rooms_cleared: u32,
    kills: u32,
    bosses: u32,
    min_hp: u32,
    room_frames: u32,
    hostiles: u32,
    towns: u32,
    victory: u32,
    ui_screen: u32,
    dodges: u32,
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
            Ok(Row {
                class: number(&record, &columns, "class")? as usize,
                max_room: number(&record, &columns, "max_room")?,
                rooms_cleared: number(&record, &columns, "rooms_cleared")?,
                kills: number(&record, &columns, "kills")?,
                bosses: number(&record, &columns, "bosses")?,
                min_hp: number(&record, &columns, "min_hp")?,
                room_frames: number(&record, &columns, "room_frames")?,
                hostiles: number(&record, &columns, "hostiles")?,
                towns: number(&record, &columns, "towns")?,
                victory: number(&record, &columns, "victory")?,
                ui_screen: number(&record, &columns, "ui_screen")?,
                dodges: number(&record, &columns, "dodges")?,
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

fn report(csv: PathBuf, runs: usize, classes: usize, min_wins: usize) -> Result<()> {
    let text = fs::read_to_string(&csv)
        .with_context(|| format!("failed to read {}", csv.display()))?;
    let rows = parse_rows(&text)?;
    let expected = runs * classes;
    println!("[balance] {}/{} agents reported", rows.len(), expected);

    let mut failures = Vec::new();
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
        let boss_clears = sample.iter().filter(|row| row.bosses > 0).count();
        let combat_stalls = sample
            .iter()
            .filter(|row| {
                row.room_frames > 3600 && row.hostiles > 0 && row.min_hp > 0 && row.victory == 0
            })
            .count();
        let route_stalls = sample
            .iter()
            .filter(|row| row.room_frames > 3600 && row.hostiles == 0 && row.victory == 0)
            .count();
        println!(
            "[balance] {name:7} n={} room_med={} clear_med={} kill_med={} boss_med={} \
             boss1={boss_clears}/{} town_med={} dodge_med={} wins={wins} endings={endings} \
             deaths={deaths} combat_stalls={combat_stalls} route_stalls={route_stalls}",
            sample.len(),
            median(sample.iter().map(|row| row.max_room)),
            median(sample.iter().map(|row| row.rooms_cleared)),
            median(sample.iter().map(|row| row.kills)),
            median(sample.iter().map(|row| row.bosses)),
            sample.len(),
            median(sample.iter().map(|row| row.towns)),
            median(sample.iter().map(|row| row.dodges)),
        );
        if wins < min_wins {
            failures.push(format!("{name} wins {wins}/{} < required {min_wins}", sample.len()));
        }
    }

    if rows.len() != expected {
        bail!("expected {expected} agent reports, found {}", rows.len());
    }
    if !failures.is_empty() {
        bail!("endurance gate FAILED: {}", failures.join("; "));
    }
    println!("[balance] raw data: {}", csv.display());
    Ok(())
}

fn main() -> Result<()> {
    match Cli::parse().command {
        Command::Report { csv, runs, classes, min_wins } => report(csv, runs, classes, min_wins),
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
    }
}

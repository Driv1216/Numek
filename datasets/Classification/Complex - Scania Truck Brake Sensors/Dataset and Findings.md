# Scania Truck Brake Sensors

Measurements from Scania trucks used to distinguish air-pressure system failures from other faults.

**Difficulty · Complex.** 60,000 training rows, 170 sensor features and a rare fault class. The label is based on the workload evaluated in Classification. [Publisher](https://archive.ics.uci.edu/dataset/421).

## Start here

- [Input - Scania Truck Brake Sensors.csv](Input%20-%20Scania%20Truck%20Brake%20Sensors.csv)
- Recommended DataTrust report — [PDF](Recommended%20-%20Rare%20air-pressure%20system%20faults.pdf) · [HTML](Recommended%20-%20Rare%20air-pressure%20system%20faults.html).

## Task and settings

Rare air-pressure system faults. The target column is `class`.

## What DataTrust found and what was checked

DataTrust found major class imbalance and widespread missing sensor values. Independent counting verified 59,409 rows with at least one missing feature and the class distribution.

## Missed coverage and limitations

It does not establish diagnostic accuracy or the cause of missing readings.

## Usefulness

Useful for deciding how to handle missingness and report minority-class metrics.

## Reproduce it manually

Open the input files above and choose this workflow in DataTrust. Use the saved field roles, declarations, and limits. The visible input names are for review. The saved configuration resolves the exact retained sources and related assets.

[Saved configuration](Technical%20Evidence/Configuration%20-%20Rare%20air-pressure%20system%20faults.json) · [Exact replay instructions](../../Technical%20Archive/Replay%20Instructions.md).

The original attempt, independent checks and earlier versions are in [Technical Evidence](Technical%20Evidence).

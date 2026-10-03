# Coordinate and Angle Conventions

## Units

- All distances and depths are in **meters**.
- Angles in the input JSON are in **degrees**.

## Coordinate frame

Each well is positioned by its collar: `east`, `north`, and `elevation`
(meters, elevation positive upward). The local frame at the collar is:

- **East**: positive toward grid east.
- **North**: positive toward grid north.
- **Down**: positive downward (into the earth).

Reported station `elevation` equals collar elevation minus cumulative
downward displacement; `tvd` is the cumulative downward displacement
(true vertical depth below the collar).

## Survey angles

- **Inclination** is measured from vertical downward, in `[0, 180]` degrees.
  `0` is straight down, `90` is horizontal, `180` is straight up.
- **Azimuth** is measured clockwise from north, in `[0, 360)` degrees.

Each station direction is the unit vector
`u = (sin(i) sin(a), sin(i) cos(a), cos(i))` in (east, north, down).

## Minimum curvature method

For a segment between stations 1 and 2 with measured-depth difference
`dmd` and direction vectors `u1`, `u2`:

- `beta = acos(clamp(dot(u1, u2), -1, 1))` — the smaller angle, `[0, pi]`.
  If `beta >= pi - 1e-8` rad the whole batch is rejected.
- Ratio factor `RF = 2 tan(beta/2) / beta`, with `RF = 1` at `beta = 0`
  and a series expansion for near-zero `beta`.
- Segment displacement: `dmd * (u1 + u2) * RF / 2`.

Displacements are accumulated from the collar. The first station (md = 0)
has zero displacement and no segment metrics (`beta_deg`,
`dogleg_per_30m` are null).

## Reported quantities

- `dogleg_per_30m`: `degrees(beta) * 30 / dmd` (degrees per 30 m).
- `horizontal_offset`: `hypot(east, north)` from the collar.
- `closure_azimuth`: bearing from collar to station, clockwise from north,
  normalized to `[0, 360)`; `null` when the offset is `<= 1e-9` m.

## Input format

```json
{
  "wells": [
    {
      "id": "W1",
      "collar": {"east": 0.0, "north": 0.0, "elevation": 100.0},
      "stations": [
        {"md": 0.0, "inclination": 0.0, "azimuth": 0.0},
        {"md": 100.0, "inclination": 10.0, "azimuth": 45.0}
      ]
    }
  ]
}
```

Well ids must be unique. Each well needs at least two stations; `md`
starts at 0 and must be strictly increasing (input order is used as-is,
no sorting). Any invalid input rejects the whole batch: the tool exits
non-zero and writes no reports.

## Output

- `stations.csv`: one row per station for all wells.
- `<well_id>.json` per well: collar, bottom-hole position, and maximum
  dogleg severity.

# Method

Sawah estimates a rice season from daily weather with four connected pieces: thermal time, reference evapotranspiration, a daily root-zone water balance, and a water-limited yield response. Each piece uses a published equation or a stated planning assumption. This page lists both.

## 1. Thermal time and growth stages

Daily growing degrees (°C·day), base 10 °C, capped at 35 °C:

    tmean = (tmin + tmax) / 2
    GDD   = min(max(tmean, 10), 35) − 10

Cumulative GDD from planting drives the stages. Total thermal time to maturity depends on the cultivar:

| Cultivar | GDD to maturity |
|---|---|
| early | 1500 |
| medium | 2000 |
| late | 2400 |

Stage boundaries are fractions of that total:

| Stage | Ends at | Crop coefficient Kc |
|---|---|---|
| vegetative | 60% | 1.10 |
| flowering | 68% | 1.20 |
| grain filling | 100% (maturity) | 0.90 |

**Assumption.** These are planning values, not measured cultivar constants. Replace them with local phenology records.

## 2. Extraterrestrial radiation and reference ET

Extraterrestrial radiation Ra (MJ m⁻² d⁻¹) follows FAO-56 (Allen et al., 1998, eq. 21):

    dr    = 1 + 0.033 cos(2π J / 365)           inverse relative Earth-Sun distance
    δ     = 0.409 sin(2π J / 365 − 1.39)        solar declination (rad)
    ωs    = arccos(−tan φ · tan δ)              sunset hour angle (rad)
    Ra    = (24·60/π) · 0.0820 · dr · (ωs sin φ sin δ + cos φ cos δ sin ωs)

where J is the day of year and φ the latitude in radians.

Reference evapotranspiration ET0 (mm d⁻¹) uses the Hargreaves–Samani form (1985), with Ra converted from MJ to mm of evaporated water by dividing by 2.45:

    ET0 = 0.0023 · (tmean + 17.8) · sqrt(tmax − tmin) · Ra / 2.45

It needs only temperature and latitude, so it works where wind and humidity records are missing. Typical tropical values are 3 to 7 mm d⁻¹. Negative results, possible only for mean temperatures below −17.8 °C, are set to zero.

## 3. Daily root-zone water balance

The root zone is a single store with capacity `C` (default 100 mm). It starts full after land preparation. Each day, with store `S`:

1. `pre = S + rain`
2. If irrigation is on and `pre < max(threshold, ETc)`, irrigation `I = max(C, ETc) − pre`. At the default settings this refills the store to `C`. Otherwise `I = 0`. Irrigated days therefore meet the full crop demand (`ETa = ETc`) and never count as stressed.
3. `available = pre + I`
4. Stress coefficient `Ks = 1` if `available ≥ threshold`, else `Ks = available / threshold`, where `threshold = f · C` and `f` is the stress fraction (default 0.5).
5. Crop evapotranspiration `ETc = Kc · ET0`, actual `ETa = min(Ks · ETc, available)`. A water-stress day is one where `ETa < ETc`. At the default settings this is the same as `Ks < 1`.
6. Drainage `D = max(0, available − ETa − C)`.
7. New store `S' = min(available − ETa, C)`.

The balance closes exactly each day: `S + rain + I = ETa + D + S'`. The test suite checks this on fixed seasons and on 300 seeded random seasons.

**Difference from FAO-56.** FAO-56 bases `Ks` on the start-of-day root-zone depletion. Sawah judges `Ks` on the water available after the day's rain and irrigation, so a day refilled by rain is counted as stressed only if the refilled water still falls short of the threshold or of the day's ETc. On days with no rain and no irrigation the two rules give the same `Ks`.

**Parameter mapping.** The stress fraction `f` equals `1 − p`, where `p` is FAO-56's depletion fraction. FAO-56 uses p = 0.5 for most crops, which is the default.

## 4. Water-limited yield

The FAO-33 response (Doorenbos & Kassam, 1979) relates relative yield to relative evapotranspiration over the season:

    Y = Ypot · (1 − Ky · (1 − ETa_total / ETc_total)), clipped to [0, Ypot]

with `Ky = 1.1`, an approximate value for rice. Sawah reports `Y` only when the crop matures inside the weather record.

**Heat.** Days with tmax ≥ 35 °C during flowering are counted and reported. They are not used in the yield, because no calibrated response exists in this model.

## What is validated, and what is not

| Component | Checked by |
|---|---|
| Radiation Ra | Expected ranges at the equator at the equinox (about 37–38 MJ m⁻² d⁻¹) and at 40°N in midsummer (about 41–42 MJ m⁻² d⁻¹) |
| Hargreaves ET0 | Term-by-term match to the equation; typical tropical range |
| Thermal time and stages | Hand-computed values; stage boundaries and maturity date on constructed weather |
| Water balance | Exact daily closure, non-negative storage and ETa ≤ ETc on fixed and on 300 seeded random seasons; rain-refilled days stressed only when the refilled water falls short of the threshold or of ETc; irrigated days meet full ETc |
| Yield | Exact match to the FAO-33 form at six potential yields and three Ky values |
| Field outcomes | **Not validated.** No field data has been compared with the model. |

## Assumptions to replace before any real decision

- Thermal times, stage fractions and Kc values are planning defaults.
- The root-zone capacity (100 mm) and stress fraction (0.5) are defaults.
- Ky = 1.1 is an approximate value.
- Irrigation water is assumed available. On irrigated days the model meets the full crop demand, so a root zone smaller than one day's ETc does not cause stress.
- Latitude is limited to ±60°.

## References

- Allen, R. G., Pereira, L. S., Raes, D., & Smith, M. (1998). *Crop evapotranspiration: guidelines for computing crop water requirements*. FAO Irrigation and Drainage Paper 56.
- Doorenbos, J., & Kassam, A. H. (1979). *Yield response to water*. FAO Irrigation and Drainage Paper 33.
- Hargreaves, G. H., & Samani, Z. A. (1985). Reference crop evapotranspiration from temperature. *Applied Engineering in Agriculture*, 1(2), 96–99.

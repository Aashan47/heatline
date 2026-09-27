"""Gate probe: can Liljegren WBGT be computed from Open-Meteo alone, and do the
NIOSH limit equations reproduce the NIOSH table?

Predictions registered before running, so a miss is a finding and not a surprise:
  P1  cossza derived as direct_radiation / direct_normal_irradiance lands in [0, 1]
      and is self-consistent, because Open-Meteo defines DNI on the beam normal.
  P2  NIOSH REL at M = 300 W gives 28.2 C, within 0.3 C of the 28 C the NIOSH
      Table 5-1 row for moderate work states for acclimatized workers.
  P3  Karachi WBGT in late September peaks somewhere in 26 to 31 C, so it sits
      near the moderate-work limits rather than far from them. If it came back at
      20 C or 40 C, something is wrong with units.
"""

import math

import httpx
import numpy as np
import thermofeel as tf

KARACHI = (24.8607, 67.0011)
KMH_TO_MS = 1000.0 / 3600.0


def niosh_rel(m_watts: float) -> float:
    """REL for acclimatized workers, degrees C WBGT.

    NIOSH 2016-106, section 8.1, verbatim:
        REL [C-WBGT] = 56.7 - 11.5 log10 M [W]
    """
    return 56.7 - 11.5 * math.log10(m_watts)


def niosh_ral(m_watts: float) -> float:
    """RAL for unacclimatized workers, degrees C WBGT.

    NIOSH 2016-106, section 8.1, verbatim:
        RAL [C-WBGT] = 59.9 - 14.1 log10 M [W]
    """
    return 59.9 - 14.1 * math.log10(m_watts)


def fetch(lat: float, lon: float):
    fields = [
        "temperature_2m", "relative_humidity_2m", "surface_pressure",
        "wind_speed_10m", "shortwave_radiation", "direct_radiation",
        "direct_normal_irradiance",
    ]
    r = httpx.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": lat, "longitude": lon, "hourly": ",".join(fields),
            "timezone": "Asia/Karachi", "forecast_days": 2,
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def main() -> None:
    print("P2: NIOSH limit equations against the NIOSH Table 5-1 moderate row")
    rel300, ral300 = niosh_rel(300), niosh_ral(300)
    print(f"  REL(300 W) = {rel300:.2f} C   table says 28 C for moderate, acclimatized")
    print(f"  RAL(300 W) = {ral300:.2f} C")
    print(f"  P2 {'PASS' if abs(rel300 - 28.0) <= 0.3 else 'FAIL'}")

    d = fetch(*KARACHI)
    h = d["hourly"]
    t = np.array(h["temperature_2m"], dtype=float)
    rh = np.array(h["relative_humidity_2m"], dtype=float)
    sp = np.array(h["surface_pressure"], dtype=float)
    va = np.array(h["wind_speed_10m"], dtype=float) * KMH_TO_MS
    ssrd = np.array(h["shortwave_radiation"], dtype=float)
    dirr = np.array(h["direct_radiation"], dtype=float)
    dni = np.array(h["direct_normal_irradiance"], dtype=float)

    # cossza from Open-Meteo's own fields: direct horizontal = DNI * cos(sza).
    cossza = np.divide(dirr, dni, out=np.zeros_like(dirr), where=dni > 0)
    fdir = np.divide(dirr, ssrd, out=np.zeros_like(dirr), where=ssrd > 0)
    print("\nP1: derived cossza")
    print(f"  range [{cossza.min():.3f}, {cossza.max():.3f}]  fdir range "
          f"[{fdir.min():.3f}, {fdir.max():.3f}]")
    ok1 = bool(cossza.min() >= 0.0 and cossza.max() <= 1.0
               and fdir.min() >= 0.0 and fdir.max() <= 1.0)
    print(f"  P1 {'PASS' if ok1 else 'FAIL'}")

    wbgt_k = tf.calculate_wbgt_liljegren(
        t2_k=t + 273.15, rh=rh, pressure=sp, va=va,
        ssrd=ssrd, fdir=fdir, cossza=cossza,
    )
    wbgt = np.asarray(wbgt_k, dtype=float) - 273.15

    print("\nP3: Karachi WBGT from the forecast")
    print(f"  WBGT range [{np.nanmin(wbgt):.1f}, {np.nanmax(wbgt):.1f}] C over "
          f"{len(wbgt)} hours")
    ok3 = bool(26.0 <= np.nanmax(wbgt) <= 31.0)
    print(f"  P3 {'PASS' if ok3 else 'FAIL, check units'}")

    peak = int(np.nanargmax(wbgt))
    print(f"\n  peak hour {h['time'][peak]}")
    print(f"    air {t[peak]:.1f} C, RH {rh[peak]:.0f}%, wind "
          f"{va[peak]:.1f} m/s, SSRD {ssrd[peak]:.0f} W/m2")
    print(f"    WBGT {wbgt[peak]:.1f} C  vs REL {rel300:.1f} C "
          f"(acclimatized), RAL {ral300:.1f} C (unacclimatized)")
    print(f"    air temp exceeds skin temp (~35 C)? "
          f"{'yes, airflow adds heat' if t[peak] > 35 else 'no'}")

    print("\n  hourly, daylight only:")
    print("    time              air   RH  wind   WBGT  vs REL")
    for i in range(len(wbgt)):
        if ssrd[i] <= 0:
            continue
        margin = wbgt[i] - rel300
        print(f"    {h['time'][i]}  {t[i]:4.1f}  {rh[i]:3.0f}  "
              f"{va[i]:4.1f}  {wbgt[i]:5.1f}  {margin:+5.1f}")


if __name__ == "__main__":
    main()

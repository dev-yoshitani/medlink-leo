# Independent orbit and contact validation

The production path is Skyfield → python-sgp4 (Vallado implementation) → Skyfield station
geometry/event search. The reference path is Pyorbital 1.12.1 `_SGDP4` → Pyorbital observer
geometry → its separate pass search. The reference does not call Skyfield or python-sgp4.
The validator calls both and compares their outputs; scalar/vector Skyfield tests remain
regression tests and are **not** counted as independent validation.

Sources: [Pyorbital implementation at v1.12.1](https://github.com/pytroll/pyorbital/blob/v1.12.1/pyorbital/orbital.py),
[observer geometry](https://github.com/pytroll/pyorbital/blob/v1.12.1/pyorbital/astronomy.py),
[API and units](https://pyorbital.readthedocs.io/en/latest/),
[Skyfield Earth satellites](https://rhodesmill.org/skyfield/earth-satellites.html).

## Reproduce

```sh
python -m pip install -e ".[dev]"
python -m medlink.experiments.orbit_validation --output artifacts/orbit-validation.json
python -m pytest tests/test_orbit_validation.py
```

The committed [machine-readable observation](assets/orbit-validation.json) contains exact
versions, TLE hash, tolerances and per-station contact counts. The sample grid covers 24 h
starting at the historical fixture epoch, with 1,441 samples at 60 s intervals. Three stations
are evaluated at 10/20 degree masks: 27 complete contacts and 54 rise/set boundaries.
The bundled epoch starts and ends outside contacts; interval-clipped and grazing passes are
not independently covered by this comparison. Near-zenith azimuth is poorly conditioned.

| Quantity | Maximum absolute/vector-norm difference | Predeclared limit |
| --- | ---: | ---: |
| TEME position | 0.002045 m | 100 m |
| TEME velocity | 0.000002305 m/s | 0.1 m/s |
| Elevation | 0.004512 deg | 0.05 deg |
| Wrapped azimuth | 0.041425 deg | 0.05 deg |
| Slant range | 44.559 m | 500 m |
| Rise/set time | 0.232256 s | 0.5 s |

Values above are rounded upward from the recorded run. TEME vectors are compared in km and
km/s then converted to SI. Reference station altitude is passed in km and geometric look
angles omit refraction. Pyorbital's Earth-rotation/observer treatment and Skyfield's time/frame
handling differ; agreement in TEME need not imply the same topocentric differences. The
angle/range differences are observed, not attributed to one source without an error budget.

These bounds catch unit/frame/time errors and check sub-timestep contact agreement for this
fixture. They do not bound real orbit error, coverage for other TLEs or deep-space objects,
or RF throughput. Both implementations share TLE data and SGP4 theory; they cannot detect a
shared incorrect physical assumption. Independent measured ephemerides, additional orbital
regimes, clipped/grazing passes and an RF propagation reference remain future work.

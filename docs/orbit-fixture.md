# Frozen orbit fixture

The offline default uses a historical International Space Station TLE copied from the official
[Skyfield Earth Satellites documentation](https://rhodesmill.org/skyfield/earth-satellites.html#loading-a-single-tle-set-from-strings).

- Satellite: ISS (ZARYA), NORAD catalog 25544
- Epoch: 2014-01-20 22:23:04 UTC
- Purpose: deterministic SGP4 and contact-window tests near the element epoch
- Network use: none

The fixture is intentionally frozen. Its propagated positions describe the documented 2014 test
scenario and must never be presented as current ISS positions. Skyfield's built-in time data is
used so the default path does not download files at runtime.

The example ground station is an illustrative reference point at 35.6895° N, 139.6917° E, 40 m
altitude. It is not represented as a real satellite operator's facility.


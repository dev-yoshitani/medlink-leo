# Link equations and units

MedLink-LEO v0.2 uses a static free-space RF link abstraction. It is not a detailed
modulation, coding, atmospheric, fading, or protocol-throughput model.

## Free-space path loss

For range \(d\) in meters and carrier frequency \(f\) in hertz:

\[
FSPL_{dB}=20\log_{10}\left(\frac{4\pi d f}{c}\right)
\]

The speed of light is \(c=299\,792\,458\;m/s\).

## Received power

All terms are expressed in dB-compatible units:

\[
P_{r,dBm}=P_{t,dBm}+G_{t,dBi}+G_{r,dBi}-FSPL_{dB}-L_{system,dB}
\]

## Thermal noise and SNR

For Boltzmann constant \(k=1.380649\times10^{-23}\;J/K\), noise temperature \(T\) in kelvin,
and channel bandwidth \(B\) in hertz:

\[
N_W=kTB
\]

\[
N_{dBm}=10\log_{10}(1000N_W)
\]

\[
SNR_{dB}=P_{r,dBm}-N_{dBm}
\]

## Capacity abstraction

The project names the Shannon result as an upper bound:

\[
C_{upper}=B\log_2(1+SNR_{linear})
\]

The simulator then uses an explicit scenario parameter:

\[
R_{effective}=\eta C_{upper},\quad 0<\eta\leq1
\]

The efficiency \(\eta\) is an engineering abstraction. `effective_rate_bps` must not be
interpreted as verified modem throughput. If a scenario supplies `required_snr_db`, link margin
is reported as `snr_db - required_snr_db`; otherwise it is `null`.


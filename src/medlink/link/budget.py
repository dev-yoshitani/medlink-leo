"""Static RF link-budget model with explicit SI units."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

from medlink.models import ensure_finite

SPEED_OF_LIGHT_M_PER_S = 299_792_458.0
BOLTZMANN_CONSTANT_J_PER_K = 1.380_649e-23


def _positive(name: str, value: float) -> float:
    checked = ensure_finite(name, value)
    if checked <= 0:
        raise ValueError(f"{name} must be > 0")
    return checked


def _derived_finite(name: str, value: float) -> float:
    if not math.isfinite(value):
        raise ValueError(f"derived {name} is not finite; check link-budget inputs")
    return value


@dataclass(frozen=True, slots=True)
class RFLinkConfig:
    """Inputs for one static link-budget calculation."""

    frequency_hz: float
    range_m: float
    tx_power_dbm: float
    tx_antenna_gain_dbi: float
    rx_antenna_gain_dbi: float
    system_losses_db: float
    noise_temperature_k: float
    channel_bandwidth_hz: float
    implementation_efficiency: float
    required_snr_db: float | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "frequency_hz",
            "range_m",
            "noise_temperature_k",
            "channel_bandwidth_hz",
        ):
            object.__setattr__(self, field_name, _positive(field_name, getattr(self, field_name)))
        for field_name in (
            "tx_power_dbm",
            "tx_antenna_gain_dbi",
            "rx_antenna_gain_dbi",
            "system_losses_db",
        ):
            object.__setattr__(
                self, field_name, ensure_finite(field_name, getattr(self, field_name))
            )
        if self.system_losses_db < 0:
            raise ValueError("system_losses_db must be >= 0")
        efficiency = ensure_finite("implementation_efficiency", self.implementation_efficiency)
        if not 0 < efficiency <= 1:
            raise ValueError("implementation_efficiency must be > 0 and <= 1")
        object.__setattr__(self, "implementation_efficiency", efficiency)
        if self.required_snr_db is not None:
            object.__setattr__(
                self,
                "required_snr_db",
                ensure_finite("required_snr_db", self.required_snr_db),
            )


@dataclass(frozen=True, slots=True)
class RFLinkTemplate:
    """Range-independent RF inputs for a dynamic link."""

    frequency_hz: float
    tx_power_dbm: float
    tx_antenna_gain_dbi: float
    rx_antenna_gain_dbi: float
    system_losses_db: float
    noise_temperature_k: float
    channel_bandwidth_hz: float
    implementation_efficiency: float
    required_snr_db: float | None = None

    def __post_init__(self) -> None:
        validated = self.at_range(1.0)
        for field_name in (
            "frequency_hz",
            "tx_power_dbm",
            "tx_antenna_gain_dbi",
            "rx_antenna_gain_dbi",
            "system_losses_db",
            "noise_temperature_k",
            "channel_bandwidth_hz",
            "implementation_efficiency",
            "required_snr_db",
        ):
            object.__setattr__(self, field_name, getattr(validated, field_name))

    def at_range(self, range_m: float) -> RFLinkConfig:
        return RFLinkConfig(
            frequency_hz=self.frequency_hz,
            range_m=range_m,
            tx_power_dbm=self.tx_power_dbm,
            tx_antenna_gain_dbi=self.tx_antenna_gain_dbi,
            rx_antenna_gain_dbi=self.rx_antenna_gain_dbi,
            system_losses_db=self.system_losses_db,
            noise_temperature_k=self.noise_temperature_k,
            channel_bandwidth_hz=self.channel_bandwidth_hz,
            implementation_efficiency=self.implementation_efficiency,
            required_snr_db=self.required_snr_db,
        )
@dataclass(frozen=True, slots=True)
class LinkBudgetResult:
    free_space_path_loss_db: float
    received_power_dbm: float
    thermal_noise_dbm: float
    snr_db: float
    channel_capacity_upper_bound_bps: float
    effective_rate_bps: float
    link_margin_db: float | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def free_space_path_loss_db(range_m: float, frequency_hz: float) -> float:
    """Return free-space path loss for meters and hertz."""
    checked_range = _positive("range_m", range_m)
    checked_frequency = _positive("frequency_hz", frequency_hz)
    value = 20.0 * (
        math.log10(4.0 * math.pi / SPEED_OF_LIGHT_M_PER_S)
        + math.log10(checked_range)
        + math.log10(checked_frequency)
    )
    return _derived_finite("free_space_path_loss_db", value)


def thermal_noise_dbm(noise_temperature_k: float, channel_bandwidth_hz: float) -> float:
    """Return kTB thermal noise in dBm."""
    temperature = _positive("noise_temperature_k", noise_temperature_k)
    bandwidth = _positive("channel_bandwidth_hz", channel_bandwidth_hz)
    value = 10.0 * (
        math.log10(BOLTZMANN_CONSTANT_J_PER_K)
        + math.log10(temperature)
        + math.log10(bandwidth)
        + 3.0
    )
    return _derived_finite("thermal_noise_dbm", value)


def _capacity_upper_bound_bps(bandwidth_hz: float, snr_db: float) -> float:
    # log1p(exp(x)) is evaluated in a stable form for very large positive SNR.
    exponent = snr_db * math.log(10.0) / 10.0
    if exponent > 50.0:
        log_one_plus_snr = exponent + math.log1p(math.exp(-exponent))
    else:
        log_one_plus_snr = math.log1p(math.exp(exponent))
    return _derived_finite(
        "channel_capacity_upper_bound_bps",
        bandwidth_hz * log_one_plus_snr / math.log(2.0),
    )


def calculate_link_budget(config: RFLinkConfig) -> LinkBudgetResult:
    """Calculate a static link budget and simplified effective rate."""
    fspl_db = free_space_path_loss_db(config.range_m, config.frequency_hz)
    received_power_dbm = _derived_finite(
        "received_power_dbm",
        config.tx_power_dbm
        + config.tx_antenna_gain_dbi
        + config.rx_antenna_gain_dbi
        - fspl_db
        - config.system_losses_db,
    )
    noise_dbm = thermal_noise_dbm(config.noise_temperature_k, config.channel_bandwidth_hz)
    snr_db = _derived_finite("snr_db", received_power_dbm - noise_dbm)
    capacity_bps = _capacity_upper_bound_bps(config.channel_bandwidth_hz, snr_db)
    effective_rate_bps = _derived_finite(
        "effective_rate_bps", config.implementation_efficiency * capacity_bps
    )
    margin_db = (
        None
        if config.required_snr_db is None
        else _derived_finite("link_margin_db", snr_db - config.required_snr_db)
    )
    return LinkBudgetResult(
        free_space_path_loss_db=fspl_db,
        received_power_dbm=received_power_dbm,
        thermal_noise_dbm=noise_dbm,
        snr_db=snr_db,
        channel_capacity_upper_bound_bps=capacity_bps,
        effective_rate_bps=effective_rate_bps,
        link_margin_db=margin_db,
    )

from __future__ import annotations

import math

import pytest

from medlink.link import (
    RFLinkConfig,
    RFLinkTemplate,
    calculate_link_budget,
    free_space_path_loss_db,
    thermal_noise_dbm,
)


def config(**overrides: float | None) -> RFLinkConfig:
    values = {
        "frequency_hz": 1.0e9,
        "range_m": 1_000.0,
        "tx_power_dbm": 30.0,
        "tx_antenna_gain_dbi": 0.0,
        "rx_antenna_gain_dbi": 0.0,
        "system_losses_db": 0.0,
        "noise_temperature_k": 290.0,
        "channel_bandwidth_hz": 1.0e6,
        "implementation_efficiency": 0.5,
        "required_snr_db": None,
    }
    values.update(overrides)
    return RFLinkConfig(**values)


def test_fspl_reference_case() -> None:
    assert free_space_path_loss_db(1_000.0, 1.0e9) == pytest.approx(92.447783, abs=1e-6)


def test_thermal_noise_reference_case() -> None:
    assert thermal_noise_dbm(290.0, 1.0e6) == pytest.approx(-113.975188, abs=1e-6)


def test_received_power_snr_and_capacity() -> None:
    result = calculate_link_budget(config())
    assert result.received_power_dbm == pytest.approx(-62.447783, abs=1e-6)
    assert result.snr_db == pytest.approx(51.527404, abs=1e-6)
    assert result.channel_capacity_upper_bound_bps == pytest.approx(17_117_043.24, rel=1e-7)
    assert result.effective_rate_bps == pytest.approx(
        result.channel_capacity_upper_bound_bps * 0.5
    )
    assert result.link_margin_db is None


def test_optional_link_margin() -> None:
    result = calculate_link_budget(config(required_snr_db=10.0))
    assert result.link_margin_db == pytest.approx(result.snr_db - 10.0)


@pytest.mark.parametrize(
    "field,value",
    [
        ("frequency_hz", 0.0),
        ("range_m", -1.0),
        ("noise_temperature_k", math.nan),
        ("channel_bandwidth_hz", math.inf),
        ("implementation_efficiency", 0.0),
        ("implementation_efficiency", 1.01),
        ("system_losses_db", -1.0),
        ("required_snr_db", math.nan),
    ],
)
def test_input_validation(field: str, value: float) -> None:
    with pytest.raises(ValueError):
        config(**{field: value})


def test_extreme_snr_capacity_remains_finite() -> None:
    result = calculate_link_budget(config(tx_power_dbm=10_000.0))
    assert math.isfinite(result.channel_capacity_upper_bound_bps)
    assert math.isfinite(result.effective_rate_bps)


def test_dynamic_template_supplies_range() -> None:
    template = RFLinkTemplate(
        frequency_hz=1.0e9,
        tx_power_dbm=30.0,
        tx_antenna_gain_dbi=0.0,
        rx_antenna_gain_dbi=0.0,
        system_losses_db=0.0,
        noise_temperature_k=290.0,
        channel_bandwidth_hz=1.0e6,
        implementation_efficiency=0.5,
    )
    near = calculate_link_budget(template.at_range(1_000.0))
    far = calculate_link_budget(template.at_range(2_000.0))
    assert near.effective_rate_bps > far.effective_rate_bps

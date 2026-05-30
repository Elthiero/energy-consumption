import logging
import random
from datetime import datetime
from typing import Dict

# Module‑level cache for cumulative energy (kWh) per meter
_cumulative_energy = {}
_last_timestamp: Dict[str, datetime] = {}


def get_time_based_multiplier(current_time: datetime) -> float:
    """
    Returns a consumption multiplier based on hour of day.
    Morning (6‑9) and evening (17‑22) peaks, low at night.
    """
    hour = current_time.hour
    if 0 <= hour < 5:
        return random.uniform(0.2, 0.4)
    elif 5 <= hour < 10:
        return random.uniform(0.8, 1.5)
    elif 10 <= hour < 17:
        return random.uniform(0.5, 0.9)
    elif 17 <= hour < 22:
        return random.uniform(1.2, 2.0)
    else:  # 22-24
        return random.uniform(0.4, 0.7)


def generate_reading(meter_id: str, current_time: datetime) -> dict:
    """
    Generate one reading for a given meter at a specific timestamp.
    Includes power (W), voltage (V), current (A), frequency (Hz), cumulative energy (kWh).
    """
    global _cumulative_energy, _last_timestamp

    mult = get_time_based_multiplier(current_time)

    # Simulate 230V grid with ±5V fluctuation
    voltage = round(random.uniform(225.0, 235.0), 2)

    # Base load 500W, scaled by time multiplier, plus random noise
    base_power = 500.0
    power = round(base_power * mult + random.uniform(-50, 50), 2)

    # I = P / V (power factor ≈ 1)
    current = round(power / voltage, 2)

    # 50 Hz grid with tiny jitter
    frequency = round(random.uniform(49.95, 50.05), 3)

    # Initialize meter if first reading
    if meter_id not in _cumulative_energy:
        _cumulative_energy[meter_id] = random.uniform(1000.0, 5000.0)
        _last_timestamp[meter_id] = current_time
        energy = _cumulative_energy[meter_id]
    else:
        # Compute time delta in seconds since last reading
        delta_seconds = (current_time - _last_timestamp[meter_id]).total_seconds()
        if delta_seconds < 0:
            # Should not happen, but guard against clock going backwards
            delta_seconds = 0
        # Energy increment: power (kW) * time (hours)
        energy_increment = (power / 1000.0) * (delta_seconds / 3600.0)
        _cumulative_energy[meter_id] += energy_increment
        _last_timestamp[meter_id] = current_time
        energy = round(_cumulative_energy[meter_id], 4)

    return {
        "meter_id": meter_id,
        "timestamp": current_time.isoformat(),
        "power": power,
        "voltage": voltage,
        "current": current,
        "frequency": frequency,
        "energy": energy,
    }

def seed_from_db(last_energies: dict, current_time: datetime):
    """
    Pre-populate the in-memory cache from DB values.
    Called once at publisher startup so live data
    continues from where historical left off.
    """
    global _cumulative_energy, _last_timestamp
    for meter_id, energy in last_energies.items():
        _cumulative_energy[meter_id] = energy
        _last_timestamp[meter_id] = current_time
    logging.info(f"Seeded {len(last_energies)} meters from DB.")


def get_all_meter_ids(count: int = 1000) -> list:
    """Return a list of string meter IDs (10 digits)."""
    base = 10_000_000_000  # 10,000,000,000 ensures 10 digits
    return [str(base + i) for i in range(count)]


def reset_simulator():
    """Reset cumulative energy cache. Call before independent simulation runs."""
    global _cumulative_energy, _last_timestamp
    _cumulative_energy = {}
    _last_timestamp = {}

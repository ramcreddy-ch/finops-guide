"""Builds a fake fleet of cloud resources and produces one CostRecord batch
per tick.

The interesting part isn't the random numbers, it's what we do with them:
a handful of resources are marked "idle" (running 24/7, barely used, but
still billed at the normal rate - that's the point) so the optimization
engine has real waste to find, and every so often a resource gets hit with
a cost spike so the anomaly detector has something to catch. Without those
two things this would just be a random number generator with extra steps.

Cost per tick comes straight from each resource's `base_cost` (an hourly
dollar figure drawn from the catalog), not from usage_quantity * unit_cost -
see the comment in simulator/catalog.py for why. usage_quantity is derived
afterwards just so the record has a plausible-looking number to show.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime

from finops.models import CostRecord
from finops.simulator.catalog import ENVIRONMENTS, PROVIDER_CATALOG, TEAMS

BUSINESS_HOURS = range(8, 19)  # 08:00-18:59, used to shape non-prod usage

# real fleets are never evenly split across environments - prod runs the
# real traffic and everything else is comparatively small
RESOURCE_COUNT_RANGE_BY_ENVIRONMENT = {
    "prod": (3, 6),
    "staging": (1, 2),
    "dev": (1, 2),
}


@dataclass
class _FleetResource:
    provider: str
    account_id: str
    environment: str
    team: str
    service: str
    unit: str
    region: str
    resource_id: str
    base_cost: float
    base_usage: float
    is_idle: bool
    normal_utilization_pct: float


@dataclass
class _ActiveAnomaly:
    resource_id: str
    factor: float
    ticks_remaining: int


@dataclass
class FleetSimulator:
    """Owns a fixed set of simulated resources and advances them tick by tick."""

    seed: int | None = None
    idle_probability: float = 0.08
    anomaly_probability_per_tick: float = 0.01
    _rng: random.Random = field(init=False, repr=False)
    _fleet: list[_FleetResource] = field(init=False, default_factory=list)
    _active_anomalies: list[_ActiveAnomaly] = field(init=False, default_factory=list)

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)
        self._fleet = self._build_fleet()

    def _build_fleet(self) -> list[_FleetResource]:
        rng = self._rng
        fleet: list[_FleetResource] = []
        for provider, cfg in PROVIDER_CATALOG.items():
            for environment in ENVIRONMENTS:
                account_id = cfg["accounts"][environment]
                for spec in cfg["services"]:
                    count = rng.randint(*RESOURCE_COUNT_RANGE_BY_ENVIRONMENT[environment])
                    for i in range(count):
                        is_idle = rng.random() < self.idle_probability
                        fleet.append(
                            _FleetResource(
                                provider=provider,
                                account_id=account_id,
                                environment=environment,
                                team=rng.choice(TEAMS),
                                service=spec.name,
                                unit=spec.unit,
                                region=rng.choice(cfg["regions"]),
                                resource_id=f"{provider}-{spec.name.lower().replace(' ', '-')}-{environment}-{i:02d}",
                                base_cost=rng.uniform(spec.cost_low, spec.cost_high),
                                base_usage=rng.uniform(spec.usage_low, spec.usage_high),
                                is_idle=is_idle,
                                normal_utilization_pct=rng.uniform(40, 85),
                            )
                        )
        return fleet

    def fleet_size(self) -> int:
        return len(self._fleet)

    def tick(self, at: datetime) -> list[CostRecord]:
        rng = self._rng
        records: list[CostRecord] = []
        self._advance_anomalies()

        for resource in self._fleet:
            cost_multiplier = self._cost_multiplier(resource, at, rng)
            anomaly_factor = self._anomaly_factor_for(resource.resource_id)
            cost = resource.base_cost * cost_multiplier * anomaly_factor

            usage = 1.0 if resource.unit == "hrs" else resource.base_usage * rng.uniform(0.85, 1.15)
            unit_cost = cost / usage if usage else cost

            tags = {"managed-by": "finops-guide-simulator"}
            if resource.unit == "hrs":
                utilization = 2.0 + rng.uniform(0, 4) if resource.is_idle else resource.normal_utilization_pct
                tags["utilization_pct"] = f"{utilization:.1f}"
            if anomaly_factor > 1.0:
                tags["anomaly"] = "true"

            records.append(
                CostRecord(
                    timestamp=at,
                    provider=resource.provider,
                    account_id=resource.account_id,
                    service=resource.service,
                    resource_id=resource.resource_id,
                    region=resource.region,
                    environment=resource.environment,
                    team=resource.team,
                    usage_type=rng.choices(
                        ["on-demand", "reserved", "spot", "savings-plan"],
                        weights=[55, 25, 10, 10],
                    )[0],
                    usage_quantity=round(usage, 4),
                    usage_unit=resource.unit,
                    unit_cost=round(unit_cost, 6),
                    cost_amount=round(cost, 4),
                    tags=tags,
                )
            )

        if rng.random() < self.anomaly_probability_per_tick and not self._active_anomalies:
            self._start_anomaly(rng)

        return records

    def _cost_multiplier(self, resource: _FleetResource, at: datetime, rng: random.Random) -> float:
        if resource.is_idle:
            # still billed at (roughly) the normal rate - that's the waste
            return rng.uniform(0.95, 1.05)

        multiplier = rng.uniform(0.85, 1.15)
        if resource.environment != "prod":
            in_hours = at.hour in BUSINESS_HOURS
            if not in_hours:
                multiplier *= rng.uniform(0.15, 0.35)
        return multiplier

    def _anomaly_factor_for(self, resource_id: str) -> float:
        for anomaly in self._active_anomalies:
            if anomaly.resource_id == resource_id:
                return anomaly.factor
        return 1.0

    def _advance_anomalies(self) -> None:
        still_active = []
        for anomaly in self._active_anomalies:
            anomaly.ticks_remaining -= 1
            if anomaly.ticks_remaining > 0:
                still_active.append(anomaly)
        self._active_anomalies = still_active

    def _start_anomaly(self, rng: random.Random) -> None:
        target = rng.choice(self._fleet)
        self._active_anomalies.append(
            _ActiveAnomaly(
                resource_id=target.resource_id,
                factor=rng.uniform(5.0, 18.0),
                ticks_remaining=rng.randint(2, 6),
            )
        )

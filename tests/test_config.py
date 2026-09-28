import copy

import pytest
import yaml

from tobacco_inspect.config import DEFAULT_CONFIG, ConfigError, load_config, parse_config


def raw():
    with open(DEFAULT_CONFIG, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def test_default_config_loads():
    cfg = load_config()
    assert cfg.solver == "gurobi"
    assert cfg.capacity.days == 5 * cfg.capacity.horizon_weeks
    assert cfg.capacity.daily_budget_minutes == cfg.capacity.hours_per_day * 60


def test_bad_solver_rejected():
    data = raw()
    data["solver"] = "cplex"
    with pytest.raises(ConfigError):
        parse_config(data)


def test_missing_key_rejected():
    data = raw()
    del data["capacity"]["teams"]
    with pytest.raises(ConfigError, match="teams"):
        parse_config(data)


@pytest.mark.parametrize(
    "bad", ["C:/Users/someone/data", "/home/someone/data", "\\\\server\\share"]
)
def test_absolute_paths_rejected(bad):
    data = copy.deepcopy(raw())
    data["paths"]["raw"] = bad
    with pytest.raises(ConfigError, match="relative"):
        parse_config(data)


def test_weights_must_sum_to_one():
    data = raw()
    data["prize"]["h_weights"]["youth_density"] = 0.9
    with pytest.raises(ConfigError):
        parse_config(data)

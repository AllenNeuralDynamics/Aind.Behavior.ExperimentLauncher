from types import ModuleType
from unittest.mock import Mock

import pytest

from clabe.launcher import collect_clabe_experiments, experiment, get_experiment_name
from clabe.launcher._experiments import _select_experiment
from tests import TESTS_ASSETS


def test_collect_clabe_experiments_discovers_decorated_function() -> None:
    experiments = list(collect_clabe_experiments(__import__("tests.assets.experiment_mock", fromlist=["*"])))
    names = {e.name for e in experiments}
    assert "simple_experiment" in names


def test_select_experiment_single_choice_uses_default_frontend() -> None:
    module_path = TESTS_ASSETS / "experiment_mock.py"
    selected = _select_experiment(module_path)
    assert selected.name == "simple_experiment"


def test_select_experiment_multiple_experiments_discovered_and_logs_constant(caplog) -> None:
    mock_frontend = Mock()
    mock_frontend.prompt_pick.return_value = "first_experiment"

    module_path = TESTS_ASSETS / "experiment_import_mocks.py"
    selected = _select_experiment(module_path, frontend=mock_frontend)

    experiments = list(collect_clabe_experiments(__import__("tests.assets.experiment_import_mocks", fromlist=["*"])))
    names = {e.name for e in experiments}
    assert {"first_experiment", "second_experiment"}.issubset(names)
    assert selected.name == "first_experiment"

    launcher = Mock()
    selected.func(launcher)


def test_select_experiment_by_name_skips_prompt() -> None:
    mock_frontend = Mock()

    module_path = TESTS_ASSETS / "experiment_import_mocks.py"
    selected = _select_experiment(module_path, frontend=mock_frontend, experiment_name="second_experiment")

    assert selected.name == "second_experiment"
    mock_frontend.prompt_pick.assert_not_called()


def test_select_experiment_by_name_raises_when_not_found() -> None:
    module_path = TESTS_ASSETS / "experiment_import_mocks.py"

    with pytest.raises(SystemExit):
        _select_experiment(module_path, frontend=Mock(), experiment_name="does_not_exist")


def test_collect_clabe_experiments_orders_by_order_field_then_declaration() -> None:
    @experiment(name="a")
    def a(launcher): ...

    @experiment(name="b")
    def b(launcher): ...

    @experiment(name="c", order=-1)
    def c(launcher): ...

    # Assignment order (a, then b, then c) mirrors declaration order in a real
    # module's namespace; "c" should still sort first via order=-1, while the
    # order=0 ties ("a", "b") keep their declaration order.
    module = ModuleType("fake_module")
    module.a, module.b, module.c = a, b, c

    experiments = list(collect_clabe_experiments(module))
    assert [e.name for e in experiments] == ["c", "a", "b"]


# --- get_experiment_name ---


def test_get_experiment_name_uses_decorator_name() -> None:
    """@experiment(name=...) takes priority over __name__."""

    @experiment(name="my_custom_name")
    def my_func(launcher): ...

    assert get_experiment_name(my_func) == "my_custom_name"


def test_get_experiment_name_falls_back_to_dunder_name() -> None:
    """Plain callable without @experiment falls back to __name__."""

    def plain_func(launcher): ...

    assert get_experiment_name(plain_func) == "plain_func"


def test_get_experiment_name_returns_none_when_no_name() -> None:
    """A callable with no __name__ and no decorator returns None."""

    nameless = Mock(spec=[])  # no __name__ attribute

    assert get_experiment_name(nameless) is None

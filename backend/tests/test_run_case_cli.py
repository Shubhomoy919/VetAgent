"""The command-line runner records the same run metadata as runs started from the app."""

from app.data.benchmark import benchmark_info
from app.scripts import run_case


def test_cli_run_records_benchmark_and_temperature(_isolated, fake_svtg):
    assert run_case.main(["BOV-WD-007", "--conditions", "C0", "--quiet"]) == 0
    runs = _isolated.list_runs()
    assert len(runs) == 1
    run, bench = runs[0], benchmark_info()
    assert run["label"] == "cli" and run["provider"] == "demo"
    assert run["benchmark_version"] == bench["version"] == "1.0.0"
    assert run["benchmark_hash"] == bench["hash"]
    assert run["temperature"] == 0.0
    assert run["force"] is False

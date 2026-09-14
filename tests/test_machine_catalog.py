import json
import pytest
from src.machine_catalog import MachineConfigError, MachineDefinition, MachineManager


def data(**changes):
    value={"host":"mint.local","scheme":"https","port":5443,"api_key":"secret",
           "auth_profile":"existing-key","default_agent":"nelly",
           "agents":["nelly","colin"],"capabilities":["development","testing"],
           "projects":{"lucy":"/srv/lucy"},"model_sources":["openai"],
           "models":["gpt-5.6-luna"]}
    value.update(changes)
    return value


def test_definition_exposes_capabilities_without_exposing_secret():
    machine=MachineDefinition.from_dict("mint",data())
    assert machine.ask_url=="https://mint.local:5443/ask"
    assert machine.supports("testing")
    assert machine.provides_agent("nelly")
    assert machine.provides_model("openai","gpt-5.6-luna")
    assert machine.project_path("lucy")=="/srv/lucy"
    assert "secret" not in repr(machine)


def test_existing_minimal_format_is_valid():
    machine=MachineDefinition.from_dict("pi",{"host":"127.0.0.1","api_key":"key","default_agent":"peace"})
    assert machine.ask_url=="http://127.0.0.1:5000/ask"
    assert machine.provides_agent("anything")


@pytest.mark.parametrize("bad,match",[
    ({"host":"x","typo":1},"unknown fields"),
    ({"host":"https://x"},"URL scheme"),
    ({"host":"x","port":70000},"between"),
    ({"host":"x","agents":["nelly"],"default_agent":"peace"},"not listed"),
])
def test_invalid_definitions_are_rejected(bad,match):
    with pytest.raises(MachineConfigError,match=match):
        MachineDefinition.from_dict("bad",bad)


def test_manager_loads_filters_and_resolves_path(tmp_path):
    path=tmp_path/"config.local.machines.json"
    path.write_text(json.dumps({"machines":{"mint":data(),"off":data(enabled=False)}}))
    manager=MachineManager(str(path))
    assert set(manager.load())=={"mint","off"}
    assert manager.get("off",require_enabled=True) is None
    assert [m.name for m in manager.eligible(agent="nelly",capability="testing",source="openai",model="gpt-5.6-luna",project="lucy")]==["mint"]
    assert MachineManager.beside_config(str(tmp_path/"config.json")).path==path


def test_missing_file_is_empty(tmp_path):
    manager=MachineManager(str(tmp_path/"missing.json"))
    assert manager.load()=={}


def test_bad_json_and_shape_are_rejected(tmp_path):
    path=tmp_path/"bad.json"
    path.write_text("{")
    with pytest.raises(MachineConfigError,match="invalid machines"):
        MachineManager(str(path)).load()
    path.write_text(json.dumps({"machines":[]}))
    with pytest.raises(MachineConfigError,match="machines must"):
        MachineManager(str(path)).load()

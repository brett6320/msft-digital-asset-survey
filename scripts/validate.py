#!/usr/bin/env python3
"""Static checks for the unpacked solution in solution/src.

Catches the mistakes that are easy to make when editing flow JSON by hand:
broken runAfter links, references to actions/parameters/variables/connections
that don't exist, and manifest entries that don't match the files on disk.
It does not prove a flow will import or run; only Power Automate can do that.
"""
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "solution" / "src"
errors = []


def err(msg):
    errors.append(msg)


def walk_actions(actions, scope_path, all_actions):
    """Collect every action name, and check runAfter within each sibling group."""
    for name, action in actions.items():
        if name in all_actions:
            err(f"{scope_path}: duplicate action name {name}")
        all_actions[name] = action
        for dep in action.get("runAfter", {}):
            if dep not in actions:
                err(f"{scope_path}/{name}: runAfter '{dep}' is not a sibling action")
        for key in ("actions",):
            if key in action:
                walk_actions(action[key], f"{scope_path}/{name}", all_actions)
        if "else" in action:
            walk_actions(action["else"].get("actions", {}), f"{scope_path}/{name}/else", all_actions)
        if "cases" in action:
            for case, body in action["cases"].items():
                walk_actions(body.get("actions", {}), f"{scope_path}/{name}/{case}", all_actions)


def check_flow(path):
    doc = json.loads(path.read_text())
    props = doc["properties"]
    definition = props["definition"]
    conn_refs = props.get("connectionReferences", {})
    params = definition.get("parameters", {})
    text = json.dumps(definition)

    all_actions = {}
    walk_actions(definition.get("actions", {}), path.name, all_actions)
    triggers = set(definition.get("triggers", {}))

    # Action references in expressions.
    for fn, name in re.findall(r"\b(outputs|body|result|actions)\('([^']+)'\)", text):
        if name not in all_actions and name not in triggers:
            err(f"{path.name}: {fn}('{name}') refers to an unknown action")
    for name in re.findall(r"\bitems\('([^']+)'\)", text):
        if all_actions.get(name, {}).get("type") != "Foreach":
            err(f"{path.name}: items('{name}') is not a Foreach")

    # Parameters, including environment variable parameters.
    for name in re.findall(r"\bparameters\('([^']+)'\)", text):
        if name not in params:
            err(f"{path.name}: parameters('{name}') is not declared")
    for name, p in params.items():
        schema = p.get("metadata", {}).get("schemaName")
        if schema and not (SRC / "environmentvariabledefinitions" / schema).is_dir():
            err(f"{path.name}: parameter '{name}' has no environment variable {schema}")

    # Variables must be initialized at the top level.
    declared = set()
    for action in definition.get("actions", {}).values():
        if action.get("type") == "InitializeVariable":
            declared.update(v["name"] for v in action["inputs"]["variables"])
    for action in all_actions.values():
        if action.get("type") in ("SetVariable", "IncrementVariable", "AppendToArrayVariable", "AppendToStringVariable"):
            if action["inputs"]["name"] not in declared:
                err(f"{path.name}: variable '{action['inputs']['name']}' is not initialized")
    for name in re.findall(r"\bvariables\('([^']+)'\)", text):
        if name not in declared:
            err(f"{path.name}: variables('{name}') is not initialized")

    # Connector actions must use a declared connection reference.
    for name, action in list(all_actions.items()) + list(definition.get("triggers", {}).items()):
        inputs = action.get("inputs")
        host = inputs.get("host") if isinstance(inputs, dict) else None
        if host:
            if host["connectionName"] not in conn_refs:
                err(f"{path.name}/{name}: connection '{host['connectionName']}' not in connectionReferences")
            if not host["apiId"].endswith("/" + host["connectionName"]):
                err(f"{path.name}/{name}: apiId does not match connectionName")
    return {r["connection"]["connectionReferenceLogicalName"] for r in conn_refs.values()}


def main():
    used_conn_refs = set()
    flow_files = sorted((SRC / "Workflows").glob("*.json"))
    for path in flow_files:
        try:
            used_conn_refs |= check_flow(path)
        except (json.JSONDecodeError, KeyError) as e:
            err(f"{path.name}: {e!r}")

    custom = ET.parse(SRC / "customizations.xml").getroot()
    manifest = ET.parse(SRC / "solution.xml").getroot()

    listed = set()
    workflow_ids = set()
    for wf in custom.iter("Workflow"):
        json_name = wf.findtext("JsonFileName").lstrip("/")
        listed.add(json_name)
        if not (SRC / json_name).is_file():
            err(f"customizations.xml: {json_name} does not exist")
        wid = wf.get("WorkflowId").strip("{}").lower()
        workflow_ids.add(wid)
        if wid.upper() not in json_name:
            err(f"customizations.xml: WorkflowId {wid} does not match {json_name}")
    for path in flow_files:
        if f"Workflows/{path.name}" not in listed:
            err(f"{path.name} is not listed in customizations.xml")

    declared_refs = {c.get("connectionreferencelogicalname") for c in custom.iter("connectionreference")}
    for ref in used_conn_refs - declared_refs:
        err(f"connection reference {ref} is used by a flow but not declared in customizations.xml")

    roots = list(manifest.iter("RootComponent"))
    root_wf = {r.get("id").strip("{}").lower() for r in roots if r.get("type") == "29"}
    root_ev = {r.get("schemaName") for r in roots if r.get("type") == "380"}
    if root_wf != workflow_ids:
        err(f"solution.xml workflow root components {sorted(root_wf)} != customizations.xml {sorted(workflow_ids)}")
    env_dirs = {p.name for p in (SRC / "environmentvariabledefinitions").iterdir() if p.is_dir()}
    if root_ev != env_dirs:
        err(f"solution.xml env var root components differ from folders: {sorted(root_ev ^ env_dirs)}")
    for d in env_dirs:
        ET.parse(SRC / "environmentvariabledefinitions" / d / "environmentvariabledefinition.xml")

    if errors:
        print("\n".join(errors))
        sys.exit(1)
    print(f"OK: {len(flow_files)} flows, {len(env_dirs)} environment variables, {len(declared_refs)} connection references")


if __name__ == "__main__":
    main()

import csv
import sys
from pathlib import Path

import pandas as pd

# append the appropriate Python module to the system path
sys.path.append(r"C:\Program Files\DIgSILENT\PowerFactory 2026 SP3\Python\3.12")

# import from the path
import powerfactory as pf


def _remove_unavailable_columns(csv_path, fixed_columns=3):
    """Drop columns whose data rows are all the '----' placeholder."""
    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f, delimiter=";"))

    if len(rows) < 2:
        return

    header, data_rows = rows[0], rows[1:]
    n_cols = len(header)

    keep = [True] * fixed_columns + [
        any(row[c].strip() != "----" for row in data_rows if c < len(row))
        for c in range(fixed_columns, n_cols)
    ]

    new_header = [v for v, k in zip(header, keep) if k]
    new_rows = [[v for v, k in zip(row, keep) if k] for row in data_rows]

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";", quoting=csv.QUOTE_ALL)
        writer.writerow(new_header)
        writer.writerows(new_rows)


def get_bus_electrical_state(busbars):
    """Read post-load-flow voltage (pu) and per-cubicle current (kA) for each busbar.

    Must be called after a successful ComLdf.Execute(). Returns a dict:
    {busbar_name: {"voltage_pu": float, "currents_kA": {connected_elm_name: float}}}
    """
    state = {}
    for busbar in busbars:
        if not busbar.IsEnergized():
            continue

        voltage_pu = busbar.GetAttribute("m:u")

        currents_ka = {}
        for cubicle in busbar.GetContents("*.StaCubic"):
            connected_elm = cubicle.obj_id
            if connected_elm is None:
                continue
            # current side ("bus1"/"bus2") matching this cubicle's connection;
            # fall back to bus1 for single-port elements (e.g. loads, shunts).
            for attr in ("m:I:bus1", "m:I:bus2"):
                try:
                    currents_ka[connected_elm.loc_name] = connected_elm.GetAttribute(attr)
                    break
                except Exception:  # pylint: disable=broad-except
                    continue

        state[busbar.loc_name] = {"voltage_pu": voltage_pu, "currents_kA": currents_ka}

    return state


def get_current_limits(busbars):
    """Read rated current (Inom, kA) for each branch element connected to each busbar.

    Elements without a thermal rating (e.g. loads) are omitted. Returns:
    {busbar_name: {connected_elm_name: Inom_kA}}
    """
    limits = {}
    for busbar in busbars:
        if not busbar.IsEnergized():
            continue

        branch_limits = {}
        for cubicle in busbar.GetContents("*.StaCubic"):
            connected_elm = cubicle.obj_id
            if connected_elm is None:
                continue
            try:
                branch_limits[connected_elm.loc_name] = connected_elm.GetAttribute("Inom")
            except Exception:  # pylint: disable=broad-except
                continue  # no thermal rating on this element type (e.g. a load)

        limits[busbar.loc_name] = branch_limits

    return limits


def measure_pv_pi_sensitivities(app, target_bus, delta_p_mw=0.01, monitor_busbars=None):
    """Finite-difference SV=dV/dP and SI=dI/dP at target_bus for a ΔP injection there.

    PowerFactory's ComVstab only exposes branch-flow/tap/loss sensitivities, not
    voltage or current sensitivity to injected power, so these are computed by
    perturbing an existing load's active power at target_bus and comparing two
    load flow solutions. Requires an ElmLod already connected to target_bus
    (this is where the energy community's injection would be modelled anyway).

    Returns {busbar_name: {"SV": float (pu/MW), "SI": {elm_name: float (kA/MW)}}}.
    """
    if monitor_busbars is None:
        monitor_busbars = [target_bus]

    ldf = app.GetFromStudyCase("ComLdf")
    if ldf is None:
        raise RuntimeError("No ComLdf command found in the study case")

    load = next(
        (
            cubicle.obj_id
            for cubicle in target_bus.GetContents("*.StaCubic")
            if cubicle.obj_id is not None
            and cubicle.obj_id.GetClassName() in ("ElmLod", "ElmLodlv")
        ),
        None,
    )
    if load is None:
        raise RuntimeError(
            f"No ElmLod connected to '{target_bus.loc_name}' to perturb; "
            "place the energy community's load/generation there first."
        )

    if ldf.Execute() != 0:
        raise RuntimeError("Baseline load flow failed")
    base_state = get_bus_electrical_state(monitor_busbars)

    original_p = load.plini
    load.plini = original_p - delta_p_mw  # reduced load == +delta_p_mw net generation

    try:
        if ldf.Execute() != 0:
            raise RuntimeError("Perturbed load flow failed")
        pert_state = get_bus_electrical_state(monitor_busbars)
    finally:
        load.plini = original_p
        ldf.Execute()  # restore the network to its original state

    sensitivities = {}
    for name, base in base_state.items():
        pert = pert_state.get(name, {})
        sv = (pert.get("voltage_pu", base["voltage_pu"]) - base["voltage_pu"]) / delta_p_mw
        si = {
            elm_name: (pert.get("currents_kA", {}).get(elm_name, i_base) - i_base) / delta_p_mw
            for elm_name, i_base in base["currents_kA"].items()
        }
        sensitivities[name] = {"SV": sv, "SI": si}

    return sensitivities


def get_coordination_payload(app, target_bus, delta_p_mw=0.01, voltage_limits_pu=(0.95, 1.05)):
    """Assemble the values the coordination component needs for one energy-community bus.

    Combines voltage/current, SV/SI sensitivities, current limits and the fixed
    voltage band into a single per-bus payload, ready to attach to an hourly
    result message.
    """
    limits = get_current_limits([target_bus]).get(target_bus.loc_name, {})
    sensitivities = measure_pv_pi_sensitivities(app, target_bus, delta_p_mw=delta_p_mw)
    state = sensitivities[target_bus.loc_name]

    ldf = app.GetFromStudyCase("ComLdf")
    if ldf.Execute() != 0:
        raise RuntimeError("Final load flow failed")
    final_state = get_bus_electrical_state([target_bus])[target_bus.loc_name]

    return {
        "bus": target_bus.loc_name,
        "voltage_pu": final_state["voltage_pu"],
        "currents_kA": final_state["currents_kA"],
        "SV": state["SV"],
        "SI": state["SI"],
        "current_limits_kA": limits,
        "voltage_limits_pu": {"min": voltage_limits_pu[0], "max": voltage_limits_pu[1]},
    }



def connect_and_activate_project(project_name):
    """Connect to PowerFactory and activate the given project. Returns the app object."""
    app = pf.GetApplicationExt()
    if app is None:
        raise RuntimeError("Could not connect to PowerFactory")

    user = app.GetCurrentUser()
    projects = user.GetContents("*.IntPrj", 1)  # recursive search
    for p in projects:
        print(p.loc_name, "->", p.GetFullPath())

    project = app.ActivateProject(project_name)

    if project != 0:  # ActivateProject returns 0 on success, 1 in case of error
        raise RuntimeError(f"Project '{project_name}' not found")

    print(f"Activated project: {project_name}")
    return app


def run_ptdf_analysis(app, results_dir=None, print_tables=True, keep_all_columns=False):
    """Run load flow + PTDF sensitivities for every busbar in the active project.

    Returns a dict mapping busbar name -> {sensitivity name: value}.
    Also writes one CSV per busbar into results_dir (if given).

    Set keep_all_columns=True to skip dropping the '----' placeholder columns,
    e.g. to inspect whether ComVstab exposes voltage/current sensitivity columns
    that are simply unpopulated with the current command configuration.
    """

    ldf = app.GetFromStudyCase("ComLdf")

    if ldf is None:
        raise RuntimeError("No ComLdf command found in the study case")

    status = ldf.Execute()

    if status != 0:
        raise RuntimeError(f"Load flow failed with return code {status}")

    print("Load flow completed")

    # -------------------------------------------------------------------------
    # Find or create the PTDF command
    # -------------------------------------------------------------------------

    study_case = app.GetActiveStudyCase()

    ptdf_command = app.GetFromStudyCase("ComVstab")

    if ptdf_command is None:
        # not present in this study case yet -> create it
        ptdf_command = study_case.CreateObject("ComVstab", "Sensitivities / Distribution Factors")

    print("PTDF command:", ptdf_command)

    # -------------------------------------------------------------------------
    # Find or create the PTDF result object
    # -------------------------------------------------------------------------

    ptdf_result = ptdf_command.pResult

    if ptdf_result is None:
        # no result object wired yet -> create one and attach it to the command
        ptdf_result = study_case.CreateObject("ElmRes", "PTDF Results")
        ptdf_command.pResult = ptdf_result

    print("PTDF result object:", ptdf_result)

    # -------------------------------------------------------------------------
    # Configure the PTDF command: which busbars to compute sensitivities for
    # -------------------------------------------------------------------------

    busbars = [
        t for t in app.GetCalcRelevantObjects("ElmTerm")
        if t.iUsage == 0  # 0 = busbar (excludes junction/internal nodes)
    ]
    if not busbars:
        raise RuntimeError("No busbars (ElmTerm with iUsage=busbar) found in the active network")

    print(f"Available busbars ({len(busbars)}):", [b.loc_name for b in busbars])

    # -------------------------------------------------------------------------
    # Create or find a result-export command (reused for every busbar)
    # -------------------------------------------------------------------------

    export_command = app.GetFromStudyCase("ComRes")

    if export_command is None:
        export_command = study_case.CreateObject("ComRes", "PTDF Export")

    if export_command is None:
        raise RuntimeError("Could not obtain a ComRes export command")

    if results_dir is not None:
        results_dir = Path(results_dir)
        results_dir.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------------------
    # Run the PTDF calculation for each busbar
    # -------------------------------------------------------------------------

    all_sensitivities = {}

    for busbar in busbars:
        if not busbar.IsEnergized():
            print(f"\nSkipping de-energised busbar: {busbar.loc_name}")
            continue

        ptdf_command.p_bus = busbar
        print(f"\nCalculating PTDF for busbar: {busbar.loc_name}")

        status = ptdf_command.Execute()

        if status != 0:
            # dump the PowerFactory output window's error messages for diagnosis
            out = app.GetOutputWindow()
            errors = out.GetContent(pf.OutputWindow.MessageType.Error)
            for msg in errors[-20:]:
                print("PF error:", msg)
            print(f"Skipping busbar '{busbar.loc_name}': PTDF calculation failed with return code {status}")
            continue

        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in busbar.loc_name)

        if results_dir is not None:
            output_file = str(results_dir / f"ptdf_{safe_name}.csv")
        else:
            output_file = str(Path.cwd() / f"ptdf_{safe_name}.csv")

        export_command.pResult = ptdf_result
        export_command.f_name = output_file

        export_command.iopt_exp = 6       # CSV format
        export_command.iopt_csel = 0      # Export all columns
        export_command.iopt_tsel = 0      # Export all rows
        export_command.iopt_honly = 0     # Export header and data
        export_command.iopt_sep = 1       # Use Windows system separator

        status = export_command.Execute()

        if status != 0:
            print(f"Skipping busbar '{busbar.loc_name}': PTDF export failed with return code {status}")
            continue

        if not keep_all_columns:
            _remove_unavailable_columns(output_file)

        print("PTDF table exported to:", output_file)

        table = pd.read_csv(output_file, sep=";", decimal=",")
        fixed_cols = ["Index", "Calculation mode", "Contingency Case Index"]

        if table.shape[1] > 3:
            values = table.drop(columns=fixed_cols).iloc[0].to_dict()
            all_sensitivities[busbar.loc_name] = values
            if print_tables:
                print(f"\n--- {busbar.loc_name} sensitivities ---")
                print(table.drop(columns=fixed_cols).T.to_string(header=False))
        else:
            all_sensitivities[busbar.loc_name] = {}
            if print_tables:
                print("(no computable sensitivities for this busbar)")

        if results_dir is None:
            Path(output_file).unlink(missing_ok=True)

    return all_sensitivities


def main():
    #PROJECT_NAME = "LV Distribution Network"
    PROJECT_NAME = "SIM_CIGREHvdcBenchmark_v2"

    app = connect_and_activate_project(PROJECT_NAME)

    RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
    run_ptdf_analysis(app, results_dir=RESULTS_DIR)

    busbars = [t for t in app.GetCalcRelevantObjects("ElmTerm") if t.iUsage == 0]
    bus_state = get_bus_electrical_state(busbars)
    for name, values in bus_state.items():
        print(name, values)


if __name__ == "__main__":
    main()
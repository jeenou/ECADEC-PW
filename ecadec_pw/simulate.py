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


def main():
    #print("Powerfactory module:", pf.__file__) # diagnostic

    #-------------------
    # Connect to Powerfactory
    #-------------------
    try:
        app = pf.GetApplicationExt()
        #print("GetApplication():", app) # diagnostic
        if app is None:
            raise RuntimeError("Could not connect to PowerFactory")

        #app_ext = pf.GetApplicationExt()
        #print("GetApplicationExt():", app_ext) # diagnostic

    except Exception as e:
        print("Exception:")
        raise

    #print(app) # diagnostic

    #------------------
    # Activate project
    #------------------
    #PROJECT_NAME = "LV Distribution Network"
    PROJECT_NAME = "SIM_CIGREHvdcBenchmark_v2"

    # List projects available to the current user (helps confirm the exact project name)
    user = app.GetCurrentUser()
    projects = user.GetContents("*.IntPrj", 1)  # recursive search
    for p in projects:
        print(p.loc_name, "->", p.GetFullPath())

    project = app.ActivateProject(PROJECT_NAME)

    if project != 0: # ActivateProject returns 0 on success, 1 in case of error
        raise RuntimeError(f"Project '{PROJECT_NAME}' not found")

    project = app.GetActiveProject()

    print(f"Activated project: {PROJECT_NAME}")

    # -----------------------------------------------------------------------------
    # Do something
    # -----------------------------------------------------------------------------

    ldf = app.GetFromStudyCase("ComLdf")
    print(ldf)

    if ldf is None:
        raise RuntimeError("No ComLdf command found in the study case")

    print("Load-flow command:", ldf)

    # List every load in the active project so the correct name can be identified
    #all_loads = app.GetCalcRelevantObjects("ElmLod")
    #print(f"Found {len(all_loads)} loads:")
    #for l in all_loads:
    #    print(" -", l.loc_name)


    # -----------------------------------------------------------------------------
    # PTDF Table
    # -----------------------------------------------------------------------------

    # -----------------------------------------------------------------------------
    # Execute load flow
    # -----------------------------------------------------------------------------

    status = ldf.Execute()

    if status != 0:
        raise RuntimeError(
            f"Load flow failed with return code {status}"
        )

    print("Load flow completed")


    # -----------------------------------------------------------------------------
    # Find or create the PTDF command
    # -----------------------------------------------------------------------------

    study_case = app.GetActiveStudyCase()

    ptdf_command = app.GetFromStudyCase("ComVstab")

    if ptdf_command is None:
        # not present in this study case yet -> create it
        ptdf_command = study_case.CreateObject("ComVstab", "Sensitivities / Distribution Factors")

    print("PTDF command:", ptdf_command)


    # -----------------------------------------------------------------------------
    # Find or create the PTDF result object
    # -----------------------------------------------------------------------------

    ptdf_result = ptdf_command.pResult

    if ptdf_result is None:
        # no result object wired yet -> create one and attach it to the command
        ptdf_result = study_case.CreateObject("ElmRes", "PTDF Results")
        ptdf_command.pResult = ptdf_result

    print("PTDF result object:", ptdf_result)


    # -----------------------------------------------------------------------------
    # Configure the PTDF command: which busbars to compute sensitivities for
    # -----------------------------------------------------------------------------

    busbars = [
        t for t in app.GetCalcRelevantObjects("ElmTerm")
        if t.iUsage == 0  # 0 = busbar (excludes junction/internal nodes)
    ]
    if not busbars:
        raise RuntimeError("No busbars (ElmTerm with iUsage=busbar) found in the active network")

    print(f"Available busbars ({len(busbars)}):", [b.loc_name for b in busbars])


    # -----------------------------------------------------------------------------
    # Create or find a result-export command (reused for every busbar)
    # -----------------------------------------------------------------------------

    export_command = app.GetFromStudyCase("ComRes")

    if export_command is None:
        export_command = study_case.CreateObject(
            "ComRes",
            "PTDF Export",
        )

    if export_command is None:
        raise RuntimeError("Could not obtain a ComRes export command")

    RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)


    # -----------------------------------------------------------------------------
    # Run the PTDF calculation for each busbar and export it to its own CSV file
    # -----------------------------------------------------------------------------

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
        output_file = str(RESULTS_DIR / f"ptdf_{safe_name}.csv")

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

        _remove_unavailable_columns(output_file)

        print("PTDF table exported to:", output_file)

        table = pd.read_csv(output_file, sep=";", decimal=",")
        if table.shape[1] > 3:
            print(f"\n--- {busbar.loc_name} sensitivities ---")
            print(table.drop(columns=["Index", "Calculation mode", "Contingency Case Index"])
                  .T.to_string(header=False))
        else:
            print("(no computable sensitivities for this busbar)")

    # -----------------------------------------------------------------------------
    # Load exported table
    # -----------------------------------------------------------------------------

    #ptdf_table = pd.read_csv(
    #    r"C:\Temp\full_ptdf.csv",
    #    sep=None,
    #    engine="python",
    #)

    #print("PTDF table shape:", ptdf_table.shape)
    #print(ptdf_table)


if __name__ == "__main__":
    main()
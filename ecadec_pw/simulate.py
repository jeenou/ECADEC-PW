import sys
import pandas as pd

# append the appropriate Python module to the system path
sys.path.append(r"C:\Program Files\DIgSILENT\PowerFactory 2026 SP3\Python\3.14")

# import from the path
import powerfactory as pf

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
PROJECT_NAME = "LV Distribution Network (16)"

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
# Find the PTDF command
# -----------------------------------------------------------------------------

ptdf_commands = app.GetFromStudyCase("ComVstab")

if ptdf_commands is None:
    raise RuntimeError(
        "No Sensitivities/Distribution Factors command "
        "(ComVstab) exists in the active study case"
    )

ptdf_command = ptdf_commands

print("PTDF command:", ptdf_command)

# diagnostic: dump current attribute values to find what's unconfigured
print("PTDF command attributes:")
for attr in ptdf_command.GetAttributeNames():
    try:
        print(f"  {attr} = {ptdf_command.GetAttribute(attr)}")
    except Exception:
        pass


# -----------------------------------------------------------------------------
# Find the PTDF result object
# -----------------------------------------------------------------------------

study_case = app.GetActiveStudyCase()

result_objects = study_case.GetContents(
    "PTDF Results.ElmRes",
    1,
)

if not result_objects:
    ptdf_result = study_case.CreateObject("ElmRes", "PTDF Results")
else:
    ptdf_result = result_objects[0]

print("PTDF result object:", ptdf_result)


# -----------------------------------------------------------------------------
# Execute the complete PTDF calculation
# -----------------------------------------------------------------------------

status = ptdf_command.Execute()

if status != 0:
    raise RuntimeError(
        f"PTDF calculation failed with return code {status}"
    )

print("PTDF calculation completed")


# -----------------------------------------------------------------------------
# Create or find a result-export command
# -----------------------------------------------------------------------------

export_command = app.GetFromStudyCase("ComRes")

if export_command is None:
    export_command = study_case.CreateObject(
        "ComRes",
        "PTDF Export",
    )

if export_command is None:
    raise RuntimeError("Could not obtain a ComRes export command")


# -----------------------------------------------------------------------------
# Export every PTDF row and column
# -----------------------------------------------------------------------------

OUTPUT_FILE = r"C:\Temp\full_ptdf.csv"

export_command.pResult = ptdf_result
export_command.f_name = OUTPUT_FILE

export_command.iopt_exp = 6       # CSV format
export_command.iopt_csel = 0      # Export all columns
export_command.iopt_tsel = 0      # Export all rows
export_command.iopt_honly = 0     # Export header and data
export_command.iopt_sep = 1       # Use Windows system separator

status = export_command.Execute()

if status != 0:
    raise RuntimeError(
        f"PTDF export failed with return code {status}"
    )

print("Whole PTDF table exported to:", OUTPUT_FILE)

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
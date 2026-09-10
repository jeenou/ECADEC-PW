import sys

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

#print(app) # diagnostic

#------------------
# Activate project
#------------------
PROJECT_NAME = "LV Distribution Network (16)"

project = app.ActivateProject(PROJECT_NAME)

if project == 1: # ActivateProject returns 0 on success, 1 in case of error
    raise RuntimeError(f"Project '{PROJECT_NAME}' not found")

print(f"Activated project: {PROJECT_NAME}")

# -----------------------------------------------------------------------------
# Do something
# -----------------------------------------------------------------------------

ldf = app.GetFromStudyCase("ComLdf")
print(ldf)

# Select the load and observed terminal by name
load = app.GetCalcRelevantObjects("LV_LD_342.ElmLod")#[0]
print(load)
#terminal = app.GetCalcRelevantObjects("Bus name.ElmTerm")[0]

# Original active power
p_original = load.plini
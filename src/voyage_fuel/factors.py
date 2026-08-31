"""Built-in fuel factor definitions."""
from decimal import Decimal
from .models import FuelDefinition, FuelFactor

def _d(path,equipment,level,mode,lcv,wt,co2,ch4,n2o,cslip=None,rwd="1",fallback=None,required=False):
    return FuelDefinition(path,equipment,level,mode,lcv,wt,co2,ch4,n2o,cslip,rwd,fallback,"",required,cslip is not None)

_DEFINITIONS = {}
def _add(*args, **kwargs):
    d = _d(*args, **kwargs); _DEFINITIONS[d.path_id] = d

for row in [
 ("HFO","HFO","A","STATIC","0.0405","13.5","3.114","0.00005","0.00018"),
 ("LFO","LFO","A","STATIC","0.041","13.2","3.151","0.00005","0.00018"),
 ("MDO","MDO","A","STATIC","0.0427","14.4","3.206","0.00005","0.00018"),
 ("MGO","MGO","A","STATIC","0.0427","14.4","3.206","0.00005","0.00018"),
 ("LNG_OTTO_MEDIUM_SPEED","LNG_OTTO_MS","A","STATIC","0.0491","18.5","2.750","0","0.00011","3.1"),
 ("LNG_OTTO_SLOW_SPEED","LNG_OTTO_SS","A","STATIC","0.0491","18.5","2.750","0","0.00011","1.7"),
 ("LNG_DIESEL_SLOW_SPEED","LNG_DIESEL_SS","A","STATIC","0.0491","18.5","2.750","0","0.00011","0.2"),
 ("LNG_LBSI","LNG_LBSI","A","STATIC","0.0491","18.5","2.750","0","0.00011","2.6"),
 ("METHANOL_NG","METHANOL_NG","A","STATIC","0.0199","31.3","1.375","0.00005","0.00018"),
 ("H2_NG_FC","H2_NG_FC","A","STATIC","0.12","132","0","0","0"),
 ("H2_NG_ICE","H2_NG_ICE","A","STATIC","0.12","132","0","0","0.00018"),
 ("LPG_PROPANE","LPG_PROPANE","B","STATIC","0.046","7.8","3.000","0.00005","0.00018","0","1",None,True),
 ("LPG_BUTANE","LPG_BUTANE","B","STATIC","0.046","7.8","3.030","0.00005","0.00018","0","1",None,True),
 ("NH3_NG_FC","NH3_NG_FC","B","STATIC","0.0186","121","0","0.00005","0.00018","0","1",None,True),
 ("NH3_NG_ICE","NH3_NG_ICE","B","STATIC","0.0186","121","0","0.00005","0.00018","0","1",None,True),
 ("BIOETHANOL","BIOETHANOL","B","BIO_E","0.02685","20","1.913","0.00005","0.00018"),
 ("BIODIESEL","BIODIESEL","B","BIO_E","0.037","20","2.834","0.00005","0.00018"),
 ("HVO","HVO","B","BIO_E","0.044","15","3.115","0.00005","0.00018"),
 ("BIOLNG_OTTO_MS","BIOLNG_OTTO_MS","B","BIO_E","0.0491","10","2.750","0","0.00011","3.1"),
 ("BIOLNG_OTTO_SS","BIOLNG_OTTO_SS","B","BIO_E","0.0491","10","2.750","0","0.00011","1.7"),
 ("BIOLNG_DIESEL_SS","BIOLNG_DIESEL_SS","B","BIO_E","0.0491","10","2.750","0","0.00011","0.2"),
 ("BIOLNG_LBSI","BIOLNG_LBSI","B","BIO_E","0.0491","10","2.750","0","0.00011","2.6"),
 ("BIOMETHANOL","BIOMETHANOL","B","BIO_E","0.01986","18","1.375","0.00005","0.00018"),
 ("BIOH2_FC","BIOH2_FC","B","CERTIFIED","0.120","25","0","0","0"),
 ("BIOH2_ICE","BIOH2_ICE","B","CERTIFIED","0.120","25","0","0","0.00018"),
 ("UCO_FAME","UCO_FAME","B","BIO_E","0.037","-61.694595","2.834","0.00005","0.00018"),
 ("E_DIESEL","E_DIESEL","B","RFNBO_E","0.0427","3","3.206","0.00005","0.00018",None,"2","MDO"),
 ("E_METHANOL","E_METHANOL","B","RFNBO_E","0.0199","3","1.375","0.00005","0.00018",None,"2","METHANOL_NG"),
 ("E_LNG_OTTO_MEDIUM_SPEED","E_LNG_OTTO_MS","B","RFNBO_E","0.0491","2","2.750","0","0.00011","3.1","2","LNG_OTTO_MEDIUM_SPEED"),
 ("E_LNG_OTTO_SLOW_SPEED","E_LNG_OTTO_SS","B","RFNBO_E","0.0491","2","2.750","0","0.00011","1.7","2","LNG_OTTO_SLOW_SPEED"),
 ("E_LNG_DIESEL_SLOW_SPEED","E_LNG_DIESEL_SS","B","RFNBO_E","0.0491","2","2.750","0","0.00011","0.2","2","LNG_DIESEL_SLOW_SPEED"),
 ("E_LNG_LBSI","E_LNG_LBSI","B","RFNBO_E","0.0491","2","2.750","0","0.00011","2.6","2","LNG_LBSI"),
 ("E_H2_FC","E_H2_FC","B","RFNBO_E","0.120","1","0","0","0",None,"2","H2_NG_FC"),
 ("E_H2_ICE","E_H2_ICE","B","RFNBO_E","0.120","1","0","0","0.00002",None,"2","H2_NG_ICE"),
 ("E_NH3_FC","E_NH3_FC","B","RFNBO_E","0.0186","2","0","0.00005","0.0001",None,"2","NH3_NG_FC",True),
 ("E_NH3_ICE","E_NH3_ICE","B","RFNBO_E","0.0186","2","0","0.00005","0.0005",None,"2","NH3_NG_ICE",True),
]: _add(*row)

# UCO-FAME uses the high-precision BIO_E derivation from the specification.
_uco = _DEFINITIONS["UCO_FAME"]
_DEFINITIONS["UCO_FAME"] = FuelDefinition(_uco.path_id, _uco.equipment_id, _uco.factor_level, _uco.wt_t_mode,
    _uco.lcv_mj_per_g, Decimal("14.9") - Decimal("2.834") / Decimal("0.037"), _uco.cf_co2_g_per_g,
    _uco.cf_ch4_g_per_g, _uco.cf_n2o_g_per_g, _uco.cslip_percent, _uco.rwd, _uco.fallback_path_id,
    _uco.category, _uco.cslip_required, _uco.methane_slip_applicable)

_ALIASES = {"LNG_OTTO_MS":"LNG_OTTO_MEDIUM_SPEED","LNG_OTTO_SS":"LNG_OTTO_SLOW_SPEED","LNG_DIESEL_SS":"LNG_DIESEL_SLOW_SPEED","E_LNG_OTTO_MS":"E_LNG_OTTO_MEDIUM_SPEED","E_LNG_OTTO_SS":"E_LNG_OTTO_SLOW_SPEED","E_LNG_DIESEL_SS":"E_LNG_DIESEL_SLOW_SPEED"}
def builtin_path_ids(): return tuple(_DEFINITIONS)
def get_definition(path_id):
    key = _ALIASES.get(str(path_id).strip().upper(), str(path_id).strip().upper())
    if key not in _DEFINITIONS: raise KeyError(f"Unsupported built-in fuel path: {path_id}")
    return _DEFINITIONS[key]
def get_builtin_factor(path_id):
    d = get_definition(path_id)
    return FuelFactor(d.path_id,d.lcv_mj_per_g,d.wt_t_g_per_mj,d.cf_co2_g_per_g,d.cf_ch4_g_per_g,d.cf_n2o_g_per_g,d.rwd,d.cslip_percent,d.methane_slip_applicable,"FIXED" if d.factor_level=="A" else "ESTIMATED")

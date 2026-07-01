import os,sys,json,time,random
sys.path.insert(0,'.')
os.environ['AETHYRO_SKIP_LICENSE']='1'
from backend.oss.financial.liquidity_routing import get_router
r=get_router()
random.seed(42)
def run(sz,rt=0.12,mut=None):
 c={'size_usd':sz,'risk_tolerance':rt,'high_volatility':True,'target_pool':'curve_usdc_eth','force_low_depth':True}
 if mut is not None:
  o=r.current_policy.get('mutation_rate')
  r.current_policy['mutation_rate']=mut
 rep=r.discover(c,shadow=True)
 if mut is not None: r.current_policy['mutation_rate']=o
 return rep
print('MUT SWEEP')
for m in [0.05,0.18,0.3,0.5]:
 rep=run(2000000,mut=m)
 print('mut',m,'gain',rep['improvement_pct'])
print('50M')
print(run(50000000)['improvement_pct'])
print('100M')
print(run(100000000)['improvement_pct'])
print('FULL TRACE 2M len',len(run(2000000)['lineage']))
rep=run(2000000)
p={'policy':rep['policy'],'gain':rep['improvement_pct'],'lineage_first':rep['lineage'][:3],'lineage_last':rep['lineage'][-3:]}
with open('data/liquidity_full_report.json','w') as ff: json.dump(p,ff,indent=2,default=str)
print('EXPORTED')

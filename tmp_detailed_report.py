import os, sys, json, time, random
sys.path.insert(0, '.')
os.environ['AETHYRO_SKIP_LICENSE'] = '1'
from backend.oss.financial.liquidity_routing import get_router
r = get_router()
random.seed(42)
def run_detailed(size, label):
    c = {'size_usd': size, 'risk_tolerance': 0.12, 'high_volatility': True, 'target_pool': 'curve_usdc_eth', 'force_low_depth': True}
    rep = r.discover(c, shadow=True)
    print('='*60)
    print('=== ' + label + ' ===')
    print('Size: $' + str(size))
    print('Gain %:', rep['improvement_pct'])
    print('P95 ms:', rep.get('p95_eval_ms'))
    print('Policy snapshot (winning run):')
    print(json.dumps(rep['policy'], indent=2))
    print()
    print('Best final allocation:')
    print(json.dumps({k: round(v,4) for k,v in rep['strategy']['allocations'].items()}, indent=2))
    print()
    print('LINEAGE WITH DELTA LOGIC (full trace):')
    for e in rep.get('lineage', []):
        gen = e['generation']
        slip = round(e['expected_slippage']*100, 4)
        dn = e.get('delta_note', '')
        al = {k.split('_')[0]: round(v*100,1) for k,v in e['allocations'].items()}
        print('  Gen ' + str(gen) + ': slip=' + str(slip) + '%   ' + str(al))
        if dn:
            print('         Delta Logic: ' + dn)
    print('='*60)
    return rep
print('=== 2M WINNING HIGH-VOL RUN ===')
run_detailed(2000000, '2M HIGH-VOL (target >12%)')
print()
print('=== 10M SCALING RUN ===')
run_detailed(10000000, '10M SCALING')

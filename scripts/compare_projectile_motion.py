"""Compare native per-age projectile states; retain LCD-timed source captures."""
import json
import sys
from pathlib import Path

def states(trace):
    result={}
    for frame in trace:
        for shot in frame['shots']:
            key=tuple(shot[k] for k in ('slot','pattern','generation','age'))
            result.setdefault(key,set()).add(tuple(sorted(shot.items())))
    return result

parent,candidate=(json.loads(Path(p).read_text()) for p in sys.argv[1:3])
assert parent['script_sha256']==candidate['script_sha256'], 'different capture scripts'
assert len(parent['traces'])==len(candidate['traces'])
for index,(before,after) in enumerate(zip(parent['traces'],candidate['traces'])):
    a,b=states(before),states(after)
    assert a==b, (index,'native projectile states changed',len(a),len(b))
print('[motion-equivalence] PASS all 13 projectile cases: same native per-age states; LCD timing is not compared')

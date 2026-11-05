# Parse accuracy (20 held-out requests)

| Parser | genre | mood | energy | likes_acoustic | activity | Field accuracy | Exact match |
| --- | --- | --- | --- | --- | --- | --- | --- |
| rules (baseline) | 90% | 100% | 95% | 95% | 90% | 94% | 75% |

## Misses: rules (baseline)
- `something chill but not lofi`: {'genre': ('lofi', None)}
- `soft piano for falling asleep`: {'activity': (None, 'sleep')}
- `angry metal, the heavier the better`: {'energy': (None, 0.95)}
- `anything except edm, something relaxing`: {'genre': ('edm', None), 'activity': ('chilling', None)}
- `euphoric club tracks, nothing acoustic`: {'likes_acoustic': (True, False)}

# Parse accuracy (20 held-out requests)

| Parser | genre | mood | energy | likes_acoustic | activity | Field accuracy | Exact match | Scored |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rules (baseline) | 90% | 100% | 95% | 95% | 90% | 94% | 75% | 20/20 |
| gemini zero-shot | 85% | 65% | 40% | 50% | 95% | 67% | 15% | 20/20 |
| gemini few-shot | 95% | 80% | 80% | 85% | 100% | 88% | 60% | 20/20 |

## Misses: rules (baseline)
- `something chill but not lofi`: {'genre': ('lofi', None)}
- `soft piano for falling asleep`: {'activity': (None, 'sleep')}
- `angry metal, the heavier the better`: {'energy': (None, 0.95)}
- `anything except edm, something relaxing`: {'genre': ('edm', None), 'activity': ('chilling', None)}
- `euphoric club tracks, nothing acoustic`: {'likes_acoustic': (True, False)}

## Misses: gemini zero-shot
- `something chill but not lofi`: {'energy': (0.3, None), 'activity': ('chilling', None)}
- `rap music for lifting weights`: {'mood': ('confident', None), 'energy': (0.9, None), 'likes_acoustic': (False, None)}
- `I want to feel like the main character on a night drive`: {'genre': ('synthwave', None), 'mood': ('confident', None), 'energy': (0.7, None), 'likes_acoustic': (False, None)}
- `soft piano for falling asleep`: {'mood': ('chill', None), 'likes_acoustic': (True, None)}
- `high energy k-pop`: {'likes_acoustic': (False, None)}
- `angry metal, the heavier the better`: {'likes_acoustic': (False, None)}
- `reggaeton for a beach party`: {'mood': ('euphoric', None), 'energy': (0.8, None), 'likes_acoustic': (False, None)}
- `romantic r&b for date night`: {'energy': (0.4, None)}
- `focus music for coding`: {'genre': ('ambient', None), 'energy': (0.3, None), 'likes_acoustic': (False, None)}
- `happy upbeat indie`: {'energy': (0.8, None)}
- `anything except edm, something relaxing`: {'energy': (0.2, None)}
- `pump-up songs for a run, really high energy`: {'mood': ('confident', None), 'likes_acoustic': (False, None)}
- `I'm heartbroken, play some blues`: {'energy': (0.3, None)}
- `classical music, energy 0.1`: {'mood': ('chill', None), 'likes_acoustic': (True, None)}
- `euphoric club tracks, nothing acoustic`: {'genre': ('edm', None), 'energy': (0.9, None)}
- `confident hip hop for walking to class`: {'energy': (0.7, None), 'likes_acoustic': (False, None)}
- `lazy sunday reggae`: {'mood': ('chill', None), 'energy': (0.2, None)}

## Misses: gemini few-shot
- `rap music for lifting weights`: {'energy': (0.9, None), 'likes_acoustic': (False, None)}
- `I want to feel like the main character on a night drive`: {'mood': ('confident', None)}
- `soft piano for falling asleep`: {'mood': ('relaxed', None), 'likes_acoustic': (True, None)}
- `angry metal, the heavier the better`: {'likes_acoustic': (False, None)}
- `happy upbeat indie`: {'energy': (0.8, None)}
- `pump-up songs for a run, really high energy`: {'mood': ('confident', None)}
- `euphoric club tracks, nothing acoustic`: {'genre': ('edm', None), 'energy': (0.9, None)}
- `lazy sunday reggae`: {'mood': ('relaxed', None), 'energy': (0.2, None)}

# 🎧 Model Card: Music Recommender Simulation

## 1. Model Name  

**VibeFinder 1.0**

---

## 2. Intended Use  

**Goal / task:** VibeFinder suggests the top 5 songs from a small catalog that best fit one listener's stated taste: a favorite genre, a favorite mood, a target energy level, and (optionally) whether they like acoustic sound.

- It assumes the user can describe their taste with those few labels and that their taste doesn't change with context (time of day, activity).
- It is built for classroom exploration of how recommenders work, not for real users.

**Intended use:** learning, demos, and experimenting with how weights change rankings.

**Not intended for:** real listeners on a real platform, decisions about which artists get promoted or paid, or anyone whose taste doesn't fit a single genre/mood label. It has no listening history, so it can't learn or personalize over time.

---

## 3. How the Model Works  

Think of it like a judge giving each song points on a scorecard:

- **Same genre as you asked for?** +2 points.
- **Same mood?** +1 point.
- **Energy:** up to +1.5 points. A song with exactly the energy you want gets all 1.5. The further away it is, the fewer points it gets. This rewards *closeness*, so a calm-music fan isn't punished for wanting low energy.
- **Acoustic sound:** up to +0.5. If you like acoustic music, more acoustic songs get more of this bonus. If you don't, more produced/electronic songs do.

Every song in the catalog gets scored this way, then the list is sorted from highest to lowest and the top 5 are shown, each with the reasons it earned its points.

**Changes from the starter:** the starter returned the first songs in the file with no scoring. I added the CSV loader, the scoring rules above, the explanation list, the ranking step, and an `--experiment` mode with different weights.

---

## 4. Data  

- **Size:** 20 songs (10 from the starter, 10 added).
- **Features per song:** genre, mood, energy, tempo (BPM), valence, danceability, acousticness. Only genre, mood, energy, and acousticness are used in scoring.
- **Added:** hip-hop, classical, metal, country, R&B, EDM, reggae, folk, blues, and K-pop, with new moods like confident, melancholy, angry, nostalgic, romantic, euphoric, and sad.
- **Limits:** 17 genres but 15 of them have only one song; lofi has 3, pop has 2. The numbers are made up, not measured from real audio. There are no lyrics, language, release year, or popularity data, and nothing about who listens to what.

---

## 5. Strengths  

- Profiles with a clear genre and mood that exist in the catalog get great results. Pop/happy → Sunrise City, Lofi/chill → Library Rain, Rock/intense → Storm Runner. These are exactly what I would pick.
- The energy-closeness rule works well as a "vibe" filter. After the genre and mood matches run out, the rest of the list is songs at a similar intensity, which feels natural (e.g., the rock fan gets EDM and metal, not classical).
- Every recommendation shows its reasons, so it's easy to see *why* a song ranked where it did.

---

## 6. Limitations and Bias 

**Main weakness found: genre dominates and is matched too literally.** A genre match is worth 2 points, more than mood and acoustic fit combined. For the "High-Energy Pop" profile, Gym Hero (pop but *intense*) ranks #2 above Starlight Sprint and Rooftop Lights, which are both *happy* and close in energy, just because Gym Hero's genre label says "pop." On top of that, genre is an exact text match, so "indie pop" and "k-pop" get zero genre credit even though a pop fan would probably enjoy them. This creates a filter bubble: the same one or two songs that share the exact label win every time, and similar-sounding music from neighboring genres is pushed down. A user whose favorite genre isn't in the catalog at all (like polka) loses the biggest bonus completely and gets generic results driven only by mood and energy.

Other limits:

- The dataset is tiny and uneven, so lofi fans get three genre matches while most other fans get one.
- Users with conflicting preferences (e.g., "sad but high energy") get a low-energy sad song at #1 because genre + mood (3 points) outweighs a bad energy match.
- Tempo, valence, and danceability are ignored, so two songs with the same labels but very different feel score the same.

---

## 7. Evaluation  

### Profiles tested

I ran five profiles with `python -m src.main`: three "normal" listeners and two adversarial edge cases.

- **High-Energy Pop:** pop, happy, energy 0.8, not acoustic
- **Chill Lofi:** lofi, chill, energy 0.35, likes acoustic
- **Deep Intense Rock:** rock, intense, energy 0.9, not acoustic
- **Conflicted:** folk, sad, energy 0.9 (sad mood but wants high energy)
- **Unknown Genre:** polka (not in the catalog), happy, energy 0.5

### Output for each profile

**High-Energy Pop**

```
================================================================
Profile: High-Energy Pop
  genre=pop, mood=happy, energy=0.8, likes_acoustic=False
----------------------------------------------------------------
1. Sunrise City by Neon Echo  [pop/happy]
   Score: 4.88
     - genre match: pop (+2.00)
     - mood match: happy (+1.00)
     - energy 0.82 vs target 0.80 (+1.47)
     - produced/electronic sound fit (+0.41)
2. Gym Hero by Max Pulse  [pop/intense]
   Score: 3.78
     - genre match: pop (+2.00)
     - energy 0.93 vs target 0.80 (+1.30)
     - produced/electronic sound fit (+0.47)
3. Starlight Sprint by NOVA9  [k-pop/happy]
   Score: 2.83
     - mood match: happy (+1.00)
     - energy 0.88 vs target 0.80 (+1.38)
     - produced/electronic sound fit (+0.45)
4. Rooftop Lights by Indigo Parade  [indie pop/happy]
   Score: 2.77
     - mood match: happy (+1.00)
     - energy 0.76 vs target 0.80 (+1.44)
     - produced/electronic sound fit (+0.33)
5. Concrete Crown by Kilo Verse  [hip-hop/confident]
   Score: 1.91
     - energy 0.78 vs target 0.80 (+1.47)
     - produced/electronic sound fit (+0.44)
```

**Chill Lofi**

```
================================================================
Profile: Chill Lofi
  genre=lofi, mood=chill, energy=0.35, likes_acoustic=True
----------------------------------------------------------------
1. Library Rain by Paper Lanterns  [lofi/chill]
   Score: 4.93
     - genre match: lofi (+2.00)
     - mood match: chill (+1.00)
     - energy 0.35 vs target 0.35 (+1.50)
     - acoustic sound fit (+0.43)
2. Midnight Coding by LoRoom  [lofi/chill]
   Score: 4.75
     - genre match: lofi (+2.00)
     - mood match: chill (+1.00)
     - energy 0.42 vs target 0.35 (+1.40)
     - acoustic sound fit (+0.35)
3. Focus Flow by LoRoom  [lofi/focused]
   Score: 3.81
     - genre match: lofi (+2.00)
     - energy 0.40 vs target 0.35 (+1.42)
     - acoustic sound fit (+0.39)
4. Spacewalk Thoughts by Orbit Bloom  [ambient/chill]
   Score: 2.85
     - mood match: chill (+1.00)
     - energy 0.28 vs target 0.35 (+1.40)
     - acoustic sound fit (+0.46)
5. Coffee Shop Stories by Slow Stereo  [jazz/relaxed]
   Score: 1.92
     - energy 0.37 vs target 0.35 (+1.47)
     - acoustic sound fit (+0.45)
```

**Deep Intense Rock**

```
================================================================
Profile: Deep Intense Rock
  genre=rock, mood=intense, energy=0.9, likes_acoustic=False
----------------------------------------------------------------
1. Storm Runner by Voltline  [rock/intense]
   Score: 4.93
     - genre match: rock (+2.00)
     - mood match: intense (+1.00)
     - energy 0.91 vs target 0.90 (+1.48)
     - produced/electronic sound fit (+0.45)
2. Gym Hero by Max Pulse  [pop/intense]
   Score: 2.93
     - mood match: intense (+1.00)
     - energy 0.93 vs target 0.90 (+1.46)
     - produced/electronic sound fit (+0.47)
3. Starlight Sprint by NOVA9  [k-pop/happy]
   Score: 1.92
     - energy 0.88 vs target 0.90 (+1.47)
     - produced/electronic sound fit (+0.45)
4. Laser Bloom by Pulse Theory  [edm/euphoric]
   Score: 1.91
     - energy 0.95 vs target 0.90 (+1.43)
     - produced/electronic sound fit (+0.48)
5. Iron Tempest by Graveforge  [metal/angry]
   Score: 1.88
     - energy 0.97 vs target 0.90 (+1.40)
     - produced/electronic sound fit (+0.48)
```

**Conflicted (sad but high energy)**

```
================================================================
Profile: Conflicted (sad but high energy)
  genre=folk, mood=sad, energy=0.9
----------------------------------------------------------------
1. Paper Boats by Juniper Hollow  [folk/sad]
   Score: 3.60
     - genre match: folk (+2.00)
     - mood match: sad (+1.00)
     - energy 0.30 vs target 0.90 (+0.60)
2. Crossroads Blue by Eddie Lark  [blues/sad]
   Score: 1.83
     - mood match: sad (+1.00)
     - energy 0.45 vs target 0.90 (+0.83)
3. Storm Runner by Voltline  [rock/intense]
   Score: 1.48
     - energy 0.91 vs target 0.90 (+1.48)
4. Starlight Sprint by NOVA9  [k-pop/happy]
   Score: 1.47
     - energy 0.88 vs target 0.90 (+1.47)
5. Gym Hero by Max Pulse  [pop/intense]
   Score: 1.46
     - energy 0.93 vs target 0.90 (+1.46)
```

**Unknown Genre (polka)**

```
================================================================
Profile: Unknown Genre (polka)
  genre=polka, mood=happy, energy=0.5
----------------------------------------------------------------
1. Rooftop Lights by Indigo Parade  [indie pop/happy]
   Score: 2.11
     - mood match: happy (+1.00)
     - energy 0.76 vs target 0.50 (+1.11)
2. Sunrise City by Neon Echo  [pop/happy]
   Score: 2.02
     - mood match: happy (+1.00)
     - energy 0.82 vs target 0.50 (+1.02)
3. Starlight Sprint by NOVA9  [k-pop/happy]
   Score: 1.93
     - mood match: happy (+1.00)
     - energy 0.88 vs target 0.50 (+0.93)
4. Dusty Porch Swing by Willa Grange  [country/nostalgic]
   Score: 1.47
     - energy 0.52 vs target 0.50 (+1.47)
5. Velvet Hours by Sade Monroe  [r&b/romantic]
   Score: 1.47
     - energy 0.48 vs target 0.50 (+1.47)
```

### Comparing profiles

- **High-Energy Pop vs. Chill Lofi:** The pop list is all songs around 0.8 energy with produced sound; the lofi list is all quiet (0.28–0.42 energy) and acoustic. This makes sense: they share no genre, no mood, and sit on opposite ends of the energy scale, so the two lists have zero songs in common.
- **High-Energy Pop vs. Deep Intense Rock:** Both want high energy, so Gym Hero and Starlight Sprint show up in both. For the pop fan, Gym Hero wins on *genre*; for the rock fan, it wins on *mood* (intense). Same song, different reason. This is why "Gym Hero" keeps showing up: it's loud, fast, and labeled pop *and* intense, so it picks up points from several kinds of listener.
- **Chill Lofi vs. Deep Intense Rock:** Total opposites. Lofi gets 3 genre matches because the catalog has 3 lofi songs; rock gets only 1 (Storm Runner), so its list falls back to "anything loud" (EDM, metal, K-pop) after the first pick. The rock fan is underserved by the data, not the math.
- **Deep Intense Rock vs. Conflicted:** Both target ~0.9 energy, and Storm Runner, Starlight Sprint, and Gym Hero appear in both. But the conflicted user's #1 is Paper Boats, a quiet folk song (0.30 energy), because matching genre + mood (3 points) beats a near-perfect energy match (1.5 points max). The system "picks a side" in the conflict, and it picks the labels.
- **Conflicted vs. Unknown Genre:** The conflicted user has a genre in the catalog, so one song gets a big head start. The polka user never gets the genre bonus, so the whole list scores low (max 2.11 out of 5) and is decided by mood and energy. Both show the system has no way to say "I don't have a good match for you."
- **High-Energy Pop vs. Unknown Genre (both "happy"):** The same three happy songs (Rooftop Lights, Sunrise City, Starlight Sprint) appear in both, but in a different order. Without the pop genre bonus, Rooftop Lights wins for the polka fan because its energy (0.76) is closest to 0.5.

### What surprised me

- Gym Hero ranked #2 for a *happy* pop fan even though its mood is *intense*. The genre label alone outweighed two songs that matched the mood.
- The conflicted "sad but high energy" profile got a quiet acoustic folk song at #1. I expected the energy target to matter more.
- Exact-match labels hide near-misses: "indie pop" got zero genre credit from a pop fan.

### Experiment: weight shift (energy ×2, genre ×½)

Run with `python -m src.main --experiment` (genre 2.0 → 1.0, energy 1.5 → 3.0).

| Profile | Baseline top 3 | Experiment top 3 | Verdict |
| --- | --- | --- | --- |
| High-Energy Pop | Sunrise City, Gym Hero, Starlight Sprint | Sunrise City, Rooftop Lights, Starlight Sprint | More accurate: happy songs beat Gym Hero |
| Chill Lofi | Library Rain, Midnight Coding, Focus Flow | Library Rain, Midnight Coding, Spacewalk Thoughts | Slightly better: chill ambient beats "focused" lofi |
| Deep Intense Rock | Storm Runner, Gym Hero, Starlight Sprint | same | No change |
| Conflicted | Paper Boats, Crossroads Blue, Storm Runner | Paper Boats, Storm Runner, Starlight Sprint | Different: high-energy songs nearly tie #1 |
| Unknown Genre | Rooftop Lights, Sunrise City, Starlight Sprint | Rooftop Lights, Sunrise City, Dusty Porch Swing | Different: energy now outranks mood |

The experiment fixed the Gym Hero problem but went too far the other way: energy became worth more than half of the possible score, so any song at the right energy gets a high floor regardless of genre or mood. I kept the original weights as the default.

### Tests

`pytest` runs the two starter tests in `tests/test_recommender.py` (pop/happy song ranks first for a pop/happy user; explanations are non-empty). Both pass.

---

## 8. Future Work  

1. **Fuzzy genre and mood matching:** give partial credit for related labels (pop ↔ indie pop ↔ k-pop, chill ↔ relaxed) instead of all-or-nothing.
2. **Diversity penalty:** stop the top 5 from being dominated by one artist or genre so users see some variety.
3. **Use more features and real behavior:** add valence and tempo to the score, and simulate likes/skips so the profile can learn over time (a first step toward collaborative filtering).
4. **"No good match" message:** when the best score is low (like the polka user's 2.11 out of 5), say so instead of pretending the results are a great fit.

---

## 9. Personal Reflection  

**Biggest learning moment:** seeing Gym Hero land at #2 for a "happy pop" listener. Nothing was broken; the code did exactly what I told it to. The problem was my weights. That made it click that a recommender's "opinions" are really the designer's choices about what counts most.

**How AI helped, and when I double-checked:** AI was fast at the repetitive parts: the CSV loader, number conversions, output formatting, and generating new songs in valid CSV format. I still had to check its work. The starter `main.py` used `from recommender import ...`, which breaks when you run `python -m src.main`, so the import had to change to `from src.recommender import ...`. I also checked the generated songs' numbers by hand (does a metal song really have 0.97 energy and almost no acousticness?) and re-ran the scoring math for the top song in each profile to confirm the points added up.

**What surprised me:** how "right" the results feel from just four rules and some addition. For the lofi and rock profiles, the lists look like something a real app would show. It made me realize a lot of what feels like intelligence in apps is careful scoring plus a clean explanation.

**What I'd try next:** fuzzy genre matching and a diversity penalty, then a tiny fake listening history (likes and skips) to compare content-based results with collaborative filtering on the same users.

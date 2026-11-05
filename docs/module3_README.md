# 🎵 Music Recommender Simulation

## Project Summary

This project is a small, CLI-first music recommender written in Python. It loads a 20-song catalog from `data/songs.csv`, compares every song to a user's "taste profile" (favorite genre, favorite mood, target energy, and whether they like acoustic sound), gives each song a score with a list of reasons, and prints the top 5. It also includes stress-test profiles and a weight experiment so you can see where the scoring logic works and where it breaks.

---

## How The System Works

### How real recommenders work

Big platforms like Spotify, YouTube, and TikTok mix two main ideas:

- **Collaborative filtering** uses other people's behavior. "Users who liked the songs you like also liked X." It relies on likes, skips, replays, saves, playlist adds, and listening time. It needs no knowledge of the music itself, but it struggles with brand-new songs or users (the "cold start" problem).
- **Content-based filtering** uses the song's own attributes, like genre, mood, tempo, energy, valence, and acousticness, and recommends songs that look similar to what you already like.

Real systems combine both, add context (time of day, device, what you just played), and learn the weights from huge amounts of data instead of hand-picking them.

### What my version prioritizes

My simulation is purely **content-based**, because there is only one user and no listening history. It prioritizes **genre** first (the strongest signal of what someone wants), then **energy closeness** (how "hype" or calm the song feels), then **mood**, with a small bonus for acoustic vs. produced sound.

### Features used

**`Song`**: `id`, `title`, `artist`, `genre`, `mood`, `energy` (0–1), `tempo_bpm`, `valence` (0–1), `danceability` (0–1), `acousticness` (0–1). The score uses `genre`, `mood`, `energy`, and `acousticness`; the others are loaded and available for future versions.

**`UserProfile`** (or the `user_prefs` dict): `favorite_genre` / `genre`, `favorite_mood` / `mood`, `target_energy` / `energy`, `likes_acoustic`.

### Algorithm Recipe

For each song (the **Scoring Rule**):

| Rule | Points |
| --- | --- |
| Genre matches exactly | +2.0 |
| Mood matches exactly | +1.0 |
| Energy closeness | `1.5 × (1 − |song energy − target energy|)` → 1.5 for a perfect match, less as the gap grows |
| Acoustic fit (only if the user set `likes_acoustic`) | `0.5 × acousticness` if they like acoustic, `0.5 × (1 − acousticness)` if not |

Max score is 5.0. Energy uses *closeness*, not "higher is better," so a calm-music fan isn't punished for wanting low energy.

Then the **Ranking Rule**: score every song in the catalog, sort from highest to lowest (ties broken by title), and return the top `k`. The scoring rule judges one song in isolation; the ranking rule is what turns those individual judgments into an ordered list of recommendations.

### Data flow

```
User prefs (genre, mood, energy, likes_acoustic)
        │
        ▼
for each song in songs.csv ──► score_song() ──► (score, reasons)
        │
        ▼
sorted() by score, highest first ──► top k ──► printed with reasons
```

### Expected biases

- Genre is worth twice as much as mood, so a same-genre song with the wrong mood can outrank a perfect mood match in a neighboring genre.
- Genre matching is exact string comparison, so `indie pop` and `k-pop` get no credit for a `pop` fan.
- With only 20 songs, most genres have exactly one song, so a user's "genre bonus" may apply to just one track.

---

## Getting Started

### Setup

1. Create a virtual environment (optional but recommended):

   ```bash
   python -m venv .venv
   source .venv/bin/activate      # Mac or Linux / Git Bash
   .venv\Scripts\Activate.ps1     # Windows PowerShell
   ```

2. Install dependencies

```bash
pip install -r requirements.txt
```

3. Run the app:

```bash
python -m src.main
```

Run the weight experiment (energy doubled, genre halved):

```bash
python -m src.main --experiment
```

Switch scoring modes (Strategy pattern): `genre-first` (default), `mood-first`, or `energy-focused`:

```bash
python -m src.main --mode mood-first
```

See [ai_interactions.md](../ai_interactions.md#design-pattern-sf10) for how the modes work and how they change the rankings.

### Running Tests

```bash
pytest
```

---

## Sample Recommendation Output

Default "pop / happy" profile from `python -m src.main`:

```
Loaded songs: 20

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

Output for all five profiles is in the [Model Card](module3_model_card.md#7-evaluation).

---

## Experiments You Tried

**Weight shift: energy doubled (1.5 → 3.0), genre halved (2.0 → 1.0).** Run with `python -m src.main --experiment`.

- **High-Energy Pop:** Gym Hero (pop but *intense*) fell from #2 to #4, and the two happy songs from other pop-adjacent genres (Rooftop Lights, Starlight Sprint) moved up. For someone who asked for *happy* pop, this felt more accurate.
- **Chill Lofi:** Spacewalk Thoughts (ambient/chill) passed Focus Flow (lofi/focused). Mood now competes with genre, which feels right for a "chill" listener.
- **Deep Intense Rock:** Same order. Storm Runner is the only rock song, and the rest were already ranked by energy.
- **Conflicted (folk/sad/0.9 energy):** Paper Boats stayed #1, but its lead shrank from 1.77 points to 0.23. High-energy songs with no matching genre or mood almost caught up.
- **Unknown Genre (polka):** Mid-energy songs (Dusty Porch Swing, Velvet Hours) jumped above Starlight Sprint even though they don't match the mood.

**Takeaway:** the change made results *different* everywhere and *more accurate* for the pop profile, but it also let energy dominate. With energy worth 3 of a possible 5.5 points, any song at the right energy level gets a high floor no matter its genre or mood. The baseline weights are kept as the default.

---

## Limitations and Risks

- Tiny catalog (20 songs), and 15 of the 17 genres have just one song.
- Exact-string genre and mood matching: `indie pop` isn't `pop`, `relaxed` isn't `chill`.
- Ignores tempo, valence, danceability, lyrics, language, and listening history.
- Can create a filter bubble: once a genre matches, the same few songs win every time.

See the [Model Card](module3_model_card.md) for more detail.

---

## Reflection

Read the full write-up in the [**Model Card**](module3_model_card.md).

Building this showed me that a "recommendation" is just a score plus a sort. The system doesn't understand music at all; it adds up points for matching labels and closeness on a couple of numbers. Even so, the top results for the pop, lofi, and rock profiles looked like what a person would pick, which is why simple systems can still feel smart.

The bias shows up in the choices I made, not in the math. Giving genre 2 points made Gym Hero beat happier songs for a "happy pop" fan, and exact string matching quietly shut out `indie pop` and `k-pop`. A user whose genre isn't in the catalog (polka) loses the biggest bonus entirely and gets generic results. In a real app, the same kind of decisions decide which artists get heard and which never show up.

# Genre Notes

Short notes about each genre, used by the retriever. `related` lists genres a fan
of this genre usually also enjoys; the recommender gives those songs partial genre
credit. `in_catalog: no` marks genres that have no songs in `data/songs.csv`, so the
system has to lean on related genres instead.

## pop
in_catalog: yes
aliases: pop music, top 40, mainstream
related: indie pop, k-pop, edm
Catchy, hook-driven songs with polished production. Pop fans usually enjoy indie pop
and k-pop, which share the same bright melodies and verse-chorus structure.

## indie pop
in_catalog: yes
aliases: indie, bedroom pop
related: pop, folk, synthwave
Pop melodies with a looser, more handmade sound. Often warmer and a bit more acoustic
than mainstream pop.

## k-pop
in_catalog: yes
aliases: kpop, korean pop
related: pop, edm, hip-hop
Korean pop: high-energy, heavily produced, dance-focused, with sharp choreography-ready beats.

## lofi
in_catalog: yes
aliases: lo-fi, lo fi, lofi hip hop, study beats
related: ambient, jazz, hip-hop
Mellow, dusty beats with soft piano and vinyl crackle. A classic choice for studying and
focus because it has steady rhythm and no distracting vocals.

## ambient
in_catalog: yes
aliases: atmospheric, drone, soundscape
related: lofi, classical
Slow, textural music without a strong beat. Very low energy; good for sleep, meditation,
and deep focus.

## jazz
in_catalog: yes
aliases: smooth jazz, coffee shop jazz
related: lofi, blues, r&b
Improvised, swinging music. Low-to-medium energy jazz works well in the background for
cooking, dinner, and coffee shops.

## classical
in_catalog: yes
aliases: orchestral, piano, symphony
related: ambient
Orchestral and solo piano music. Usually very acoustic and low energy; common for reading,
studying, and calm evenings.

## rock
in_catalog: yes
aliases: rock music, alt rock, alternative, punk
related: metal, blues
Guitar-driven music with live drums. High-energy rock is a staple of workout playlists.

## metal
in_catalog: yes
aliases: heavy metal, metalcore
related: rock
Loud, distorted, very high-energy music. Fits angry or intense moods and hard workouts.

## synthwave
in_catalog: yes
aliases: synth, retrowave, outrun
related: edm, indie pop
Retro 80s-style synthesizers and drum machines. Moody and cinematic; a common pick for
night drives.

## hip-hop
in_catalog: yes
aliases: hip hop, hiphop, rap, trap
related: r&b, lofi, k-pop
Rhythm and rapped vocals over beats. Confident, medium-high energy.

## r&b
in_catalog: yes
aliases: rnb, r and b, soul, neo soul
related: hip-hop, jazz
Smooth vocals and grooves. Often romantic and medium-low energy.

## edm
in_catalog: yes
aliases: electronic dance, house, techno, trance, dubstep
related: pop, k-pop, synthwave
Electronic dance music built for clubs: very high energy, euphoric drops, almost never acoustic.

## country
in_catalog: yes
aliases: country music, americana, bluegrass
related: folk, blues
Story-driven songs with acoustic guitar and fiddle. Often nostalgic, medium energy.

## folk
in_catalog: yes
aliases: singer-songwriter, acoustic folk
related: country, indie pop, blues
Acoustic, lyric-focused music. Usually low energy and very acoustic; often sad or reflective.

## blues
in_catalog: yes
aliases: delta blues
related: jazz, rock, country
Twelve-bar songs about hard times. Sad or soulful, low-to-medium energy.

## reggae
in_catalog: yes
aliases: dub, ska
related: hip-hop, r&b
Laid-back off-beat rhythm. Relaxed, sunny, medium energy; a beach and summer staple.

## polka
in_catalog: no
aliases: oompah
related: folk, country
Upbeat accordion dance music from Central Europe. Not in the catalog; the closest sounds
are folk and country, which share the acoustic instruments and dance rhythms.

## latin
in_catalog: no
aliases: reggaeton, salsa, bachata, cumbia
related: reggae, pop, edm
Danceable Latin American styles. Not in the catalog; reggae and pop share the rhythm-first feel.

## gospel
in_catalog: no
aliases: worship, choir
related: r&b, blues
Choir-led spiritual music. Not in the catalog; r&b and blues share its vocal style.

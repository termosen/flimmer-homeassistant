<img src="icon.png" alt="Flimmer" width="96" align="right">

# Flimmer for Home Assistant

The household's Flimmer server in Home Assistant: what plays where, whether
the server holds the IPTV provider, the library, the transcoders -- updated
the moment the server says something changed -- and the televisions with
Flimmer open as media players (films, episodes, channels and music, with artist and album), to pause, resume and stop.

## Install

With HACS: HACS → ⋮ → Custom repositories → `https://github.com/termosen/flimmer-homeassistant`,
type Integration → install Flimmer → restart Home Assistant.

By hand: copy `custom_components/flimmer` into Home Assistant's `config/custom_components/`
and restart Home Assistant.

## Set up

1. In Flimmer: Settings → Mine → Keys → make a key named "Home Assistant".
2. In Home Assistant: Settings → Devices & services. The server is usually
   found by itself; otherwise Add integration → Flimmer, with its address
   (http://<server>:8080) and the key.

## What you get

- Sensors: Streams (with every session as an attribute), Now playing,
  Players on, Films, Series, Albums, Newest title, IPTV held by; for an
  admin's key also Transcoding, CPU and Memory.
- Binary sensors: Watching, Watching live TV, Playing music, Holds the IPTV provider,
  All servers online.
- A media player for each television where Flimmer is open: playing, paused,
  idle (open, nothing playing) or off; pause, play, stop, next and previous.
- Services `flimmer.play` (title_id or channel_id, on a player) and
  `flimmer.play_music` (album_id, artist_id or track_id).
- An event `flimmer_change` on every change the server tells about (type:
  playing, library, channels, favourites, resume, ...), for automations.

Example: dim the living-room lights when a film starts on Office:

```yaml
automation:
  - alias: Film on Office dims the lights
    triggers:
      - trigger: state
        entity_id: media_player.office
        to: playing
    conditions:
      - condition: state
        entity_id: media_player.office
        attribute: kind
        state: vod
    actions:
      - action: light.turn_on
        target: { entity_id: light.living_room }
        data: { brightness_pct: 15 }
```

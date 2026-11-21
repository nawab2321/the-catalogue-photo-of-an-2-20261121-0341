# Nimbus No. 2

[![make.fun · the-catalogue-photo-of-an-2-20261121-0341](https://make.fun/badge/the-catalogue-photo-of-an-2-20261121-0341.svg)](https://make.fun/bounty/the-catalogue-photo-of-an-2-20261121-0341?utm_source=github&utm_medium=readme&utm_campaign=the-catalogue-photo-of-an-2-20261121-0341)
[![rank](https://make.fun/badge/the-catalogue-photo-of-an-2-20261121-0341/nawab2321/the-catalogue-photo-of-an-2-20261121-0341/rank.svg)](https://make.fun/bounty/the-catalogue-photo-of-an-2-20261121-0341/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=the-catalogue-photo-of-an-2-20261121-0341)
[![reward](https://make.fun/badge/the-catalogue-photo-of-an-2-20261121-0341/nawab2321/the-catalogue-photo-of-an-2-20261121-0341/reward.svg)](https://make.fun/bounty/the-catalogue-photo-of-an-2-20261121-0341?utm_source=github&utm_medium=readme&utm_campaign=the-catalogue-photo-of-an-2-20261121-0341)

A benchtop punch for clouds. Original procedural 3D artwork, path-traced with Blender Cycles. The cloud is volumetric, with cylindrical cuts carved into its density field.

[View the full-resolution render](assets/nimbus.jpg)

## Run the entry

`python3 main.py` writes the packaged JPEG to the contest's `/output/entry.png` using the Python standard library. Set `NIMBUS_OUTPUT_DIR` for a local output directory.

## Render from source

Run with Blender 4.5 and FFmpeg from the repository root.

```sh
blender --background --threads 14 --python scene.py -- --out /tmp/nimbus-render.png
ffmpeg -hide_banner -loglevel error -y -i /tmp/nimbus-render.png \
  -vf 'scale=out_color_matrix=bt601:out_range=full,format=yuvj444p' \
  -map_metadata -1 -frames:v 1 -c:v mjpeg -threads 1 -qmin 1 -q:v 1 \
  -update 1 assets/nimbus.jpg
```

# Frigate tuning guide

Copy-paste snippets for common tuning tasks. All YAML is valid for Frigate 0.14+
(including 0.17). Do NOT paste these into `config.example.yml` — that file is the
minimal working starting point. Put them in your live `config.yml`.

---

## 1. Zones — restrict alerts to one area of the frame

### Why

Without zones, Frigate alerts on any person or car anywhere in the frame,
including the public footpath or road across the street. A zone lets you say
"only alert when the object is inside my driveway."

### How to get coordinates

1. Open the Frigate UI at `http://localhost:5000`.
2. Go to **Cameras → your camera → Debug**.
3. Click **Bounding Box** to overlay the frame, then use the **Zone editor**
   (or draw a polygon manually) to capture pixel coordinates.
   Coordinates are listed as comma-separated `x,y` pairs, relative to the
   frame's **detect** resolution (the substream width × height you set in
   `detect:`).

### Snippet

```yaml
cameras:
  front_door:
    # … ffmpeg, detect, record, snapshots as normal …

    zones:
      driveway:
        # Four-corner polygon. Replace with coordinates from the Frigate UI.
        # Format: x1,y1,x2,y2,x3,y3,x4,y4  (pixel coords, detect resolution)
        coordinates: 50,480,320,240,480,240,640,480
        objects:
          # Optional: only objects in this list count for this zone.
          - person
          - car

    review:
      alerts:
        # Only generate an alert when the object is inside one of these zones.
        required_zones:
          - driveway
```

**Result:** a person standing on the public sidewalk outside your driveway polygon
will be detected and recorded but will NOT trigger an alert (and will not fire
`alert_watcher.py`).

---

## 2. Motion masks — ignore a waving tree, flag, or busy road

A motion mask tells Frigate's motion detector to ignore movement in a region of
the frame. This cuts wasted CPU cycles and reduces false-positive detections from
trees, flags, or a road in the background.

```yaml
cameras:
  front_door:
    # … other config …

    motion:
      # List of polygons to mask out of motion detection.
      # Same coordinate format as zones (pixel coords at detect resolution).
      mask:
        - 0,0,160,0,160,120,0,120       # top-left corner — e.g. a waving flag
        - 480,360,640,360,640,480,480,480  # bottom-right corner — e.g. a busy road
```

Tips:
- Keep masks as small as possible; masking the whole right half of the frame
  means no detection there at all.
- After editing, restart Frigate and watch the **Motion** overlay in the debug
  view to confirm the masked region is grey.

---

## 3. Detectors — faster inference with OpenVINO or hardware accelerators

### OpenVINO CPU detector (drop-in upgrade, no extra hardware)

The default `cpu` detector uses a TFLite model on the CPU. Frigate's OpenVINO
detector uses Intel's inference engine, which is meaningfully faster on the same
CPU (especially Intel silicon) with no additional hardware.

```yaml
detectors:
  ov:
    type: openvino
    device: CPU        # or GPU for an Intel iGPU, or AUTO

# The model block is TOP-LEVEL (a sibling of detectors:), NOT nested under it.
model:
  width: 300
  height: 300
  input_tensor: nhwc
  input_pixel_format: bgr
  path: /openvino-model/ssdlite_mobilenet_v2.xml
  labelmap_path: /openvino-model/coco_91cl_bkgr.txt
```

The model files ship inside the Frigate Docker image at those paths — no download
needed. Replace the `detectors: cpu1:` block in your `config.yml` with the
`detectors: ov:` block above, AND add the top-level `model:` block.

**Note on heavier loads (many cameras or a weaker CPU):**
- **Google Coral TPU** (`device: usb` or `device: pci`) — 100+ inferences/sec,
  passes to the host via USB or M.2. Best option for 4+ camera setups.
- **Intel iGPU** (`device: GPU`) — OpenVINO can offload to an integrated Intel
  GPU. Add the GPU device to the Frigate container in `docker-compose.yml`
  (uncomment the `devices:` lines already in the example).
- See `https://docs.frigate.video/configuration/detectors` for the full list.

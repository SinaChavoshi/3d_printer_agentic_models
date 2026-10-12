# Generated Models

This directory contains the 3D models published by this project.

## Organization
Each model lives in `openscad/<model>/`:
- `<model>.scad`: the parametric OpenSCAD source.
- `<model>.stl` (or one STL per part for multi-part models): print-ready binary STL.
- `render.png`: the thumbnail, and `README.md` with a description, download links and an OpenSCAD Playground link.

## 📦 STL Files
Every model includes print-ready STL files, so you can download and print without installing OpenSCAD. They are rendered from the `.scad` with its default settings. Other 3D artifacts (`.obj`, `.3mf`, `.gcode`, ...) are still ignored by git.

After changing a `.scad`, regenerate its STL and thumbnail:

```bash
python tools/render_scad/export_stl.py generated_models/openscad/<model>
./tools/render_scad/render.sh generated_models/openscad/<model>/<model>.scad
```

## OpenSCAD Models Gallery

| Model Name | Thumbnail | STL |
| :--- | :--- | :--- |
| [Battery Holders (AA & AAA)](openscad/battery_holders) | <img src="openscad/battery_holders/render.jpg" width="150" /> | [AA](openscad/battery_holders/aa_battery_holder.stl) · [AAA](openscad/battery_holders/aaa_battery_holder.stl) |
| [Box Fan Window Mount Bracket](openscad/box_fan_window_mount_bracket) | <img src="openscad/box_fan_window_mount_bracket/render.png" width="150" /> | [⬇️ STL](openscad/box_fan_window_mount_bracket/box_fan_window_mount_bracket.stl) |
| [Coffee Filter Mold](openscad/coffee_filter_mold) | <img src="openscad/coffee_filter_mold/render.png" width="150" /> | [⬇️ STL](openscad/coffee_filter_mold/coffee_filter_mold.stl) |
| [Door Jamb Hanger](openscad/door_hanger) | <img src="openscad/door_hanger/render.png" width="150" /> | [⬇️ STL](openscad/door_hanger/door_hanger.stl) |
| [Fishing Hoochie Wiggler](openscad/fishing_hoochie_wiggler) | <img src="openscad/fishing_hoochie_wiggler/render.png" width="150" /> | [⬇️ STL](openscad/fishing_hoochie_wiggler/fishing_hoochie_wiggler.stl) |
| [Fishing Scent Holder](openscad/fishing_scent_holder) | <img src="openscad/fishing_scent_holder/render.png" width="150" /> | [⬇️ STL](openscad/fishing_scent_holder/fishing_scent_holder.stl) |
| [Diamond Fishing Spoon](openscad/fishing_spoon) | <img src="openscad/fishing_spoon/render.png" width="150" /> | [⬇️ STL](openscad/fishing_spoon/fishing_spoon.stl) |
| [Gas Can Cap](openscad/gas_can_cap) | <img src="openscad/gas_can_cap/render.png" width="150" /> | [⬇️ STL](openscad/gas_can_cap/gas_can_cap.stl) |
| [Hexagonal Table Organizer](openscad/hexagonal_table_organizer) | <img src="openscad/hexagonal_table_organizer/render.png" width="150" /> | [⬇️ STL](openscad/hexagonal_table_organizer/hexagonal_table_organizer.stl) |
| [High Heel Door Wedge](openscad/high_heel_door_wedge) | <img src="openscad/high_heel_door_wedge/render.png" width="150" /> | [⬇️ STL](openscad/high_heel_door_wedge/high_heel_door_wedge.stl) |
| [AI-Optimized King Salmon Cut-Plug Lure](openscad/king_salmon_cut_plug) | <img src="openscad/king_salmon_cut_plug/render.png" width="150" /> | [⬇️ STL](openscad/king_salmon_cut_plug/king_salmon_cut_plug.stl) |
| [Circular Leitner Box](openscad/leitner_box) | <img src="openscad/leitner_box/render.png" width="150" /> | [rim](openscad/leitner_box/leitner_box_rim.stl) · [lid](openscad/leitner_box/leitner_box_lid.stl) · [peg](openscad/leitner_box/leitner_box_day_marker_peg.stl) |
| [Lipgloss Organizer](openscad/lipgloss_organizer) | <img src="openscad/lipgloss_organizer/render.png" width="150" /> | [⬇️ STL](openscad/lipgloss_organizer/lipgloss_organizer.stl) |
| [Square Lipstick Organizer](openscad/lipstick_organizer) | <img src="openscad/lipstick_organizer/render.png" width="150" /> | [⬇️ STL](openscad/lipstick_organizer/lipstick_organizer.stl) |
| [Rugged Enclosure](openscad/rugged_enclosure) | <img src="openscad/rugged_enclosure/render.png" width="150" /> | [body](openscad/rugged_enclosure/rugged_enclosure_body.stl) · [lid](openscad/rugged_enclosure/rugged_enclosure_lid.stl) · [latch ×2](openscad/rugged_enclosure/rugged_enclosure_latch.stl) |
| [Salmon Fishing Spoon](openscad/salmon_fishing_spoon) | <img src="openscad/salmon_fishing_spoon/render.png" width="150" /> | [⬇️ STL](openscad/salmon_fishing_spoon/salmon_fishing_spoon.stl) |
| [Siding Light Mount](openscad/siding_light_mount) | <img src="openscad/siding_light_mount/render.png" width="150" /> | [⬇️ STL](openscad/siding_light_mount/siding_light_mount.stl) |
| [Toy Screwdriver Handle](openscad/toy_screwdriver_handle) | <img src="openscad/toy_screwdriver_handle/render.png" width="150" /> | [⬇️ STL](openscad/toy_screwdriver_handle/toy_screwdriver_handle.stl) |
| [Window Exhaust Adapter](openscad/window_exhaust_adapter) | <img src="openscad/window_exhaust_adapter/render.png" width="150" /> | [left](openscad/window_exhaust_adapter/window_exhaust_adapter_left_male.stl) · [right](openscad/window_exhaust_adapter/window_exhaust_adapter_right_female.stl) |
| [WOLFBOX G840S Rear Camera Mount](openscad/wolfbox_rear_camera_mount) | <img src="openscad/wolfbox_rear_camera_mount/render.png" width="150" /> | [⬇️ STL](openscad/wolfbox_rear_camera_mount/wolfbox_rear_camera_mount.stl) |

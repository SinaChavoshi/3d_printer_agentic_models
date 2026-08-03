$fn = 60;

// --- TARGET DIMENSIONS & GRID ---
target_depth = 202.856;     // Fixed Y depth to match existing organizer
cols = 3;                   // Count per row
rows = 5;                   // Total active rows
wall_thickness = 12.0;      // Generous spacing between slots
base_thickness = 4.0;       // Solid bottom floor thickness (no through-holes)

// --- LIPGLOSS SLOT PARAMETERS ---
slot_diameter = 24.0;       // Diameter of the lipgloss tube
slot_angle = 50.0;          // Tilt angle from vertical (50 = lays flatter)
total_height = 42.0;        // Solid block height
bevel_size = 1.0;           // 1mm smooth transition chamfer at the top rim

// --- HORIZONTAL MARGINS & WIDTH ---
col_pitch = slot_diameter + wall_thickness;
side_margin = 12.0;         // Thick outer side walls prevent odd-row stagger breakthroughs

// Total width safely absorbs the odd-row rightward shift (col_pitch / 2)
total_width = (side_margin * 2) + (cols * col_pitch) + (col_pitch / 2) - wall_thickness;
total_depth = target_depth;

// --- PERIMETER-CORRECTED DEPTH & TRIGONOMETRIC CLAMPING ---
slot_r = slot_diameter / 2;

// 1. Clamp cylinder travel using the LOWEST EDGE of the perimeter
max_vertical_drop = total_height - base_thickness;
slot_length_z = (max_vertical_drop - (slot_r * sin(slot_angle))) / cos(slot_angle);

// 2. Safe maximum horizontal reach per slot
max_horizontal_reach = 30.0;
slot_length_y = (max_horizontal_reach - (slot_r * cos(slot_angle))) / sin(slot_angle);

// Use the safer minimum length so the floor is never breached
slot_length = min(slot_length_z, slot_length_y);

// 3. Calculate exact Y footprint of a single slot and the full 5-row layout
single_slot_y_span = (slot_length * sin(slot_angle)) + (slot_r * cos(slot_angle));
ellipse_forward_reach = slot_r / cos(slot_angle);

// Space rows evenly
y_stride = 32.0;
total_layout_depth = ellipse_forward_reach + ((rows - 1) * y_stride) + single_slot_y_span;

// 4. Center the layout front-to-back by splitting remaining depth equally
y_margin = (target_depth - total_layout_depth) / 2;
front_margin = y_margin + ellipse_forward_reach;

// --- MODEL GENERATION ---
module lipgloss_50deg_centered_organizer() {
    difference() {
        // 1. SOLID BOUNDING BLOCK
        cube([total_width, total_depth, total_height]);

        // 2. 50-DEGREE ANGLED CYLINDERS WITH UNIFIED SUBTRACTIVE CUTS
        for (r = [0 : rows - 1]) {
            row_x_offset = (r % 2 == 0) ? 0 : (col_pitch / 2);
            for (c = [0 : cols - 1]) {
                x_center = side_margin + row_x_offset + (c * col_pitch) + slot_r;
                y_center = front_margin + (r * y_stride);

                translate([x_center, y_center, total_height]) {
                    
                    // Main body cut extending downward
                    rotate([-slot_angle, 0, 0]) {
                        translate([0, 0, -slot_length])
                            cylinder(h = slot_length + 20, d = slot_diameter);
                    }
                    
                    // Smooth transition (bevel) tightly constrained to the top 1mm
                    hull() {
                        // Top edge: perfectly flush with the Z=42 surface, flared out by bevel_size
                        translate([0, 0, 0])
                            linear_extrude(0.01)
                            offset(r = bevel_size)
                            scale([1, 1 / cos(slot_angle)])
                            circle(d = slot_diameter);
                            
                        // Bottom edge: exactly matches the tilted cylinder 1mm down, naturally shifted backward
                        translate([0, -bevel_size * tan(slot_angle), -bevel_size])
                            linear_extrude(0.01)
                            scale([1, 1 / cos(slot_angle)])
                            circle(d = slot_diameter);
                    }
                }
            }
        }
    }
}

lipgloss_50deg_centered_organizer();

$fn = 60; // Higher number = smoother curves

// --- PARAMETERS ---
// Target Dimensions to match Hex Organizer
target_depth = 202.856; // Forces the block to be exactly this deep

// Lipstick slot dimensions
slot_width = 22;        // Width of the slot
slot_depth = 22;        // Depth of the slot
slot_height = 25.0;     // Height of the block
corner_radius = 2.0;    // How much to round the corners

// Label Ramp dimensions
ramp_height = 3.0;      // How high the ramp rises
gap_before_slot = 1.0;  // Gap between ramp end and slot

// Grid configuration
cols = 4;
rows = 6;

// Structural settings
wall_thickness = 4;
base_thickness = 2.0;

// --- CALCULATIONS ---
// Calculate label_depth automatically to ensure total_depth perfectly matches target_depth
label_depth = ((target_depth - wall_thickness) / rows) - slot_depth - wall_thickness;

y_stride = label_depth + slot_depth + wall_thickness;
total_width = wall_thickness + cols * (slot_width + wall_thickness);
total_depth = wall_thickness + (rows * y_stride); 
total_height = slot_height + base_thickness;

// Output dimensions to the console
echo(str("Total Width (X): ", total_width, " mm"));
echo(str("Total Depth (Y): ", total_depth, " mm"));
echo(str("Total Height (Z): ", total_height, " mm"));

// --- MODULES ---
// Creates a rounded square for cutouts and footprints
module rounded_square(size, r) {
    offset(r = r) square([size[0] - 2*r, size[1] - 2*r], center = true);
}

// --- MODEL GENERATION ---
module lipstick_organizer() {
    union() {
        
        // 1. MAIN BLOCK WITH ROUNDED CUTOUTS
        difference() {
            cube([total_width, total_depth, total_height]);
            
            for (r = [0 : rows - 1]) {
                for (c = [0 : cols - 1]) {
                    // Center point of the slot
                    x_slot = wall_thickness + (c * (slot_width + wall_thickness)) + (slot_width/2);
                    y_slot = wall_thickness + (r * y_stride) + label_depth + (slot_depth/2);
                    
                    translate([x_slot, y_slot, base_thickness])
                    linear_extrude(slot_height + 1)
                        rounded_square([slot_width, slot_depth], corner_radius);
                }
            }
        }
        
        // 2. INTERSECTED ROUNDED RAMPS
        for (r = [0 : rows - 1]) {
            for (c = [0 : cols - 1]) {
                
                ramp_length = label_depth - gap_before_slot;
                
                // Center point of the ramp footprint
                x_center = wall_thickness + (c * (slot_width + wall_thickness)) + (slot_width/2);
                y_ramp_center = wall_thickness + (r * y_stride) + (ramp_length/2);
                
                translate([x_center, y_ramp_center, total_height])
                intersection() {
                    // Shape A: The perfectly rounded footprint extruded straight up
                    linear_extrude(ramp_height) 
                        rounded_square([slot_width, ramp_length], corner_radius);
                    
                    // Shape B: The slanted wedge (made slightly wider to ensure a clean cut)
                    translate([-(slot_width + 2)/2, -ramp_length/2, 0])
                    hull() {
                        // Front edge (flat on surface)
                        cube([slot_width + 2, 0.01, 0.01]);
                        // Back edge (raised to ramp_height)
                        translate([0, ramp_length - 0.01, 0])
                            cube([slot_width + 2, 0.01, ramp_height]);
                    }
                }
            }
        }
    }
}

lipstick_organizer();
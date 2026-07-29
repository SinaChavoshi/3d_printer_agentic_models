// --- CUSTOMIZABLE PARAMETERS ---
$fn = 100;                  // Smoothness of curves

// Main Dimensions
inner_diameter = 45.0;      // Inner diameter of the cap walls
wall_thickness = 3.0;       // Thickness of the cap walls
cap_height = 25.0;          // Total height of the cap
top_thickness = 4.0;        // Thickness of the top lip holding the spout down

// Spout Cutout
spout_hole_diameter = 35.0; // The hole in the top for the spout to poke through

// Edge Rounding
edge_rounding = 1.0;        // Radius of the rounded edges (fillet)

// Thread Settings
thread_pitch = 5.0;         // Distance from thread ridge to ridge
thread_depth = 2.0;         // Maximum depth of the thread at its peak
thread_turns = 3;           // Number of full rotations for the thread
thread_resolution = 80;     // Smoothness of the thread sweep
taper_turns = 0.1;          // How many turns it takes for the thread to taper to zero

// --- THE MODEL ---

union() {
    // 1. Main rounded collar body
    rotate_extrude(angle = 360, $fn = 100) {
        // The double offset trick perfectly rounds outer (convex) corners
        offset(r = edge_rounding)
        offset(delta = -edge_rounding)
        polygon([
            [inner_diameter / 2, 0],
            [(inner_diameter / 2) + wall_thickness, 0],
            [(inner_diameter / 2) + wall_thickness, cap_height],
            [spout_hole_diameter / 2, cap_height],
            [spout_hole_diameter / 2, cap_height - top_thickness],
            [inner_diameter / 2, cap_height - top_thickness]
        ]);
    }

    // 2. Rounded External Ribs (Pill shape)
    for (i = [0 : 15 : 360]) {
        rotate([0, 0, i])
        translate([(inner_diameter / 2) + wall_thickness - 0.5, 0, 0])
        hull() {
            // Top and bottom spheres to create a smoothly rounded rib
            translate([0, 0, edge_rounding]) sphere(d = 3);
            translate([0, 0, cap_height - edge_rounding]) sphere(d = 3);
        }
    }

    // 3. The Tapered 3D Triangular Internal Threads
    translate([0, 0, 2]) // Start 2mm above the bottom edge
    v_thread_tapered(id = inner_diameter, pitch = thread_pitch, max_depth = thread_depth, turns = thread_turns, res = thread_resolution, taper = taper_turns);
}

// --- MODULES ---

// Sweeps a 3D triangle along a helical path, dynamically tapering the ends
module v_thread_tapered(id, pitch, max_depth, turns, res, taper) {
    steps = turns * res;
    angle_step = 360 / res;
    z_step = pitch / res;
    taper_steps = taper * res;
    
    // Function to calculate depth: scales linearly during the tapers
    function calc_depth(i) = 
        (i <= taper_steps) ? max(0.01, max_depth * (i / taper_steps)) :
        (i >= steps - taper_steps) ? max(0.01, max_depth * ((steps - i) / taper_steps)) :
        max_depth;

    for(i = [0 : steps - 1]) {
        d1 = calc_depth(i);
        d2 = calc_depth(i + 1);
        
        hull() {
            rotate([0, 0, i * angle_step])
            translate([0, 0, i * z_step])
            thread_profile(id, d1, pitch);
            
            rotate([0, 0, (i + 1) * angle_step])
            translate([0, 0, (i + 1) * z_step])
            thread_profile(id, d2, pitch);
        }
    }
}

// The core 3D triangle shape for the thread
module thread_profile(id, current_depth, pitch) {
    translate([id / 2 + 0.5, 0, 0]) 
    rotate([90, 0, 0])
    linear_extrude(height = 0.1, center = true)
    polygon([ [0, pitch/2.2], [-current_depth, 0], [0, -pitch/2.2] ]);
}
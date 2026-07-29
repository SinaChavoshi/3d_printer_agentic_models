// --- PARAMETERS ---
$fn = 100;                  // High resolution for smooth 3D printing curves

num_bottles = 4;            // 4 bottles in a row
bottle_diameter = 35;       // Internal diameter of each round hole
wall_thickness = 4;         // Substantial wall thickness to allow a nice rolled rim
cup_height = 30;            // Total height of the holder
base_floor_thickness = 2;   // Solid bottom floor

// Smoothing controls
top_roll_radius = 2.0;      // Radius of the outward rolled top rim (Bullnose)
body_corner_radius = 5;     // Smooth outer corners of the main block

// Derived dimensions
cup_outer_dia = bottle_diameter + (wall_thickness * 2);
pitch = bottle_diameter + wall_thickness; 
total_length = ((num_bottles - 1) * pitch) + cup_outer_dia;

// --- MAIN ASSEMBLY ---
difference() {
    
    // 1. SOLID MAIN BODY WITH ROLLED OUTER EDGES
    union() {
        // Main flat-sided block (built up to just below the roll)
        linear_extrude(height = cup_height - top_roll_radius) {
            rounded_block_profile_2d();
        }
        
        // The positive Outward Rolled Rim Cap for the outer edge
        translate([0, 0, cup_height - top_roll_radius]) {
            minkowski() {
                linear_extrude(height = 0.01) {
                    rounded_block_profile_2d(shrink = top_roll_radius);
                }
                difference() {
                    sphere(r = top_roll_radius);
                    translate([0, 0, -top_roll_radius]) 
                        cube(top_roll_radius * 2, center = true);
                }
            }
        }
    }
    
    // 2. ROUND HOLES & INDIVIDUAL OUTWARD ROLLED LIPS
    for (i = [0 : num_bottles - 1]) {
        let(cX = i * pitch + cup_outer_dia / 2, cY = cup_outer_dia / 2) {
            
            // Main vertical circular cavity
            translate([cX, cY, base_floor_thickness]) {
                cylinder(h = cup_height + 2, d = bottle_diameter);
            }
            
            // OUTWARD HOLE ROLL: Carves a smooth radius outward from the hole rim
            translate([cX, cY, cup_height - top_roll_radius]) {
                difference() {
                    // Temporary solid cylinder to carve from
                    cylinder(h = top_roll_radius + 0.1, d = bottle_diameter + (top_roll_radius * 2));
                    
                    // Keep the inner hole clear
                    translate([0, 0, -0.1])
                        cylinder(h = top_roll_radius + 0.5, d = bottle_diameter);
                    
                    // The donut cutting tool that carves the outward flare
                    translate([0, 0, top_roll_radius]) {
                        rotate_extrude() {
                            translate([(bottle_diameter / 2) + top_roll_radius, 0, 0]) {
                                circle(r = top_roll_radius);
                            }
                        }
                    }
                }
            }
        }
    }
}

// --- 2D PROFILE GENERATOR (ROUNDED RECTANGLE TRACK) ---
module rounded_block_profile_2d(shrink = 0) {
    offset(r = body_corner_radius - shrink) {
        offset(r = -body_corner_radius) {
            hull() {
                translate([cup_outer_dia / 2, cup_outer_dia / 2])
                    circle(d = cup_outer_dia);
                
                translate([total_length - (cup_outer_dia / 2), cup_outer_dia / 2])
                    circle(d = cup_outer_dia);
            }
        }
    }
}
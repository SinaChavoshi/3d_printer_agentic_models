/* 32-Day Spaced Repetition 'Compact Vault'
   Optimized for 54mm x 70mm cards STANDING UPRIGHT.
   FEATURES: 
   - 216mm max footprint (Maxed for Prusa CORE One)
   - Completely domed U-Shaped track dividers
   - 3-Layer optimized walls & floor for hyper-fast printing
   - Deep 1mm Snap-Fit with reinforced top collar
   - Merged 32-1-2 Window (Eliminates fragile micro-dividers)
   - Filleted Lid Prongs (Smooth rounded outer tips using 2D offset)
   - Support-free teardrop marker holes & matching printable peg
*/

$fn = 120; // High resolution for FDM curves

// --- CORE PARAMETERS ---
card_width = 54;   // Exact width
card_height = 70;  // Exact height
margin = 1;        // 1mm extra space for height and width

// Rim Dimensions (Perfectly tuned for 0.4mm nozzle to eliminate gap-fill)
wall_thickness = 1.26;  // Exactly 3 perimeters (0.42mm line width x 3)
divider_thickness = 0.86; // Exactly 2 perimeters 
base_thickness = 0.84;    // Exactly 3 layers (at 0.28mm layer height)

// --- COMPACT RADIUS MATH ---
// Outer radius is LOCKED to 108mm (216mm diameter maxing out 220mm Y-axis)
outer_radius = 108; 

track_width = card_width + margin; // 55mm
inner_radius = outer_radius - track_width - (wall_thickness * 2); 
rim_height = card_height + margin + 12; // Encloses the 71mm clearance + lid mechanism

// Dynamically scale lid to cover exactly 2/3 of the track width
lid_outer_radius = inner_radius + wall_thickness + (track_width * (2/3));
lid_thickness = 4;

// System Math
days = 32;
angle_per_day = 360 / days;

// Transition windows mapping for text placement
marker_positions = [0, 1, 3, 7, 15, 31]; 
marker_labels = ["1", "2", "4", "8", "16", "32"]; 

// --- PRINT SPLITTING TOOL ---
// 0 = View Whole Assembly 
// 1 = Render Secure Lid Only
// 2 = Render Main Base Only
// 3 = Render Day Marker Peg Only
print_mode = 0; 


// --- RENDER LOGIC ---
if (print_mode == 0) {
    color("SteelBlue") main_rim();
    color("Orange") translate([0, 0, rim_height]) lid();
    color("Red") translate([outer_radius + 4, 0, rim_height - 12]) rotate([0, 90, 0]) day_marker_peg();
} else if (print_mode == 1) {
    lid();
} else if (print_mode == 2) {
    main_rim();
} else if (print_mode == 3) {
    day_marker_peg();
}


// --- UTILITY MODULES ---

// 2D drafting module for precise wedge window subtractions
module wedge_2d(r1, r2, a) {
    difference() {
        circle(r=r2);
        circle(r=r1);
        // Masks out everything outside the target angle 'a'
        rotate([0, 0, a]) translate([-r2, 0]) square([r2*2, r2*2]);
        translate([-r2, -r2*2]) square([r2*2, r2*2]);
        translate([-r2*2, -r2]) square([r2*2, r2*2]);
    }
}

// Support-free elongated oval for marker pegs
module teardrop_slot(w, h, depth) {
    translate([0, 0, -h/2]) 
    rotate([90, 0, 90])
    linear_extrude(height=depth, center=true) {
        hull() {
            translate([0, w/2]) circle(d=w, $fn=30); // Rounded bottom
            translate([-w/2, h - w]) square([w, 0.1]); // Straight sides
            translate([0, h]) polygon([[-0.1, 0], [0.1, 0], [0, 0.1]]); // Pointy top for safe overhangs
        }
    }
}

// 2D Profile for the fully curved U-Shape divider
module u_divider_2d(w, h, pw, base_h) {
    cw = w - 2 * pw; // Width of inner cutout
    cr = cw / 2;     // Radius of the U-curve at the bottom
    
    union() {
        square([w, base_h]);
        
        difference() {
            square([w, base_h + cr]);
            translate([pw + cr, base_h + cr]) circle(r=cr, $fn=60);
            translate([pw, base_h + cr]) square([cw, h]); 
        }
        
        // Left Pillar (Fully Domed Top)
        translate([pw/2, base_h]) 
        hull() {
            square([pw, 0.1], center=true);
            translate([0, h - base_h - pw/2]) circle(d=pw, $fn=30); 
        }
        
        // Right Pillar (Fully Domed Top)
        translate([w - pw/2, base_h]) 
        hull() {
            square([pw, 0.1], center=true);
            translate([0, h - base_h - pw/2]) circle(d=pw, $fn=30); 
        }
    }
}


// --- MAIN MODULES ---

module main_rim() {
    difference() {
        union() {
            // Inner Wall
            difference() {
                union() {
                    cylinder(r=inner_radius + wall_thickness, h=rim_height);
                    // Thickened Reinforcement Collar (Top 10mm)
                    translate([0, 0, rim_height - 10]) cylinder(r=inner_radius + 3.0, h=10);
                }
                translate([0, 0, -1]) cylinder(r=inner_radius, h=rim_height + 2);
            }
            
            // Outer Wall
            difference() {
                cylinder(r=outer_radius, h=rim_height);
                translate([0, 0, -1]) cylinder(r=outer_radius - wall_thickness, h=rim_height + 2);
            }
            
            // Floor
            difference() {
                cylinder(r=outer_radius, h=base_thickness);
                translate([0, 0, -1]) cylinder(r=inner_radius, h=base_thickness + 2);
            }
            
            // The 32 Domed U-Shaped Day Dividers
            divider_h = rim_height * 0.8; 
            pillar_w = 8;  
            base_h = 10;   
            
            for(i = [0 : days - 1]) {
                rotate([0, 0, i * angle_per_day]) {
                    translate([inner_radius, divider_thickness/2, base_thickness]) {
                        rotate([90, 0, 0]) { 
                            linear_extrude(height=divider_thickness) {
                                u_divider_2d(
                                    w = track_width + (wall_thickness*2), 
                                    h = divider_h, 
                                    pw = pillar_w, 
                                    base_h = base_h
                                );
                            }
                        }
                    }
                }
            }
        }
        
        // --- BASE SNAP-FIT GROOVE (1.2mm deep total) ---
        translate([0, 0, rim_height - 5]) {
            rotate_extrude() {
                translate([inner_radius, 0, 0]) circle(d=2.4, $fn=30); 
            }
        }
        
        // --- BASE DAY TICKS ---
        for(i = [0 : days - 1]) {
            rotate([0, 0, i * angle_per_day]) {
                translate([outer_radius, 0, rim_height - 12]) {
                    teardrop_slot(w=3.5, h=8, depth=wall_thickness*4); 
                }
            }
        }
    }
}

module lid() {
    difference() {
        union() {
            // 1. Main Cover Plate (Drafted in 2D to enable automatic outer corner filleting)
            linear_extrude(height=lid_thickness) {
                // Fillet trick: Shrinking then expanding rounds all sharp outer tips perfectly
                offset(r=2.5) offset(r=-2.5) {
                    difference() {
                        circle(r=lid_outer_radius);
                        circle(r=inner_radius - 6); // Clean wide-open center
                        
                        // --- MERGED WINDOW: Days 32, 1, and 2 ---
                        // Starts at sector 31, cleanly sweeps across 3 full sectors
                        rotate([0, 0, 31 * angle_per_day + 0.5]) 
                            wedge_2d(inner_radius + 2, lid_outer_radius + 5, (3 * angle_per_day) - 1);
                            
                        // Window: Day 4
                        rotate([0, 0, 3 * angle_per_day + 0.5]) 
                            wedge_2d(inner_radius + 2, lid_outer_radius + 5, angle_per_day - 1);
                            
                        // Window: Day 8
                        rotate([0, 0, 7 * angle_per_day + 0.5]) 
                            wedge_2d(inner_radius + 2, lid_outer_radius + 5, angle_per_day - 1);
                            
                        // Window: Day 16
                        rotate([0, 0, 15 * angle_per_day + 0.5]) 
                            wedge_2d(inner_radius + 2, lid_outer_radius + 5, angle_per_day - 1);
                    }
                }
            }
            
            // 2. Inner Stabilizing Cylinder & Snap-Fit Ring
            translate([0, 0, -15]) {
                difference() {
                    union() {
                        cylinder(r=inner_radius - 0.4, h=15); 
                        translate([0, 0, 10]) { 
                            rotate_extrude() {
                                translate([inner_radius - 0.4, 0, 0]) circle(d=2.0, $fn=30); 
                            }
                        }
                    }
                    translate([0, 0, -1]) cylinder(r=inner_radius - 6, h=17);
                }
            }
        }
        
        // --- SUBTRACTING TEXT LABELS ---
        // Numbers remain exactly under their corresponding slots on the thick inner ring
        for(i = [0 : 5]) {
            a = marker_positions[i] * angle_per_day;
            rotate([0, 0, a + (angle_per_day / 2)]) {
                translate([inner_radius - 2.0, 0, lid_thickness -3]) {
                    rotate([0, 0, -90]) { 
                        linear_extrude(6) {
                            text(marker_labels[i], size=6, font="Arial:style=Bold", halign="center", valign="center");
                        }
                    }
                }
            }
        }
    }
}

// --- MODULE: Day Marker Peg (Highly Robust Wedge-Lock Version) ---
module day_marker_peg() {
    // Target hole dimensions are 3.5mm x 8.0mm
    // Base is fractionally oversized (3.55mm) to force a tight locking wedge
    base_w = 3.55; 
    base_h = 8.05;
    shaft_length = 6.0; // Lengthened slightly for deeper, more secure wall engagement
    tip_scale = 0.72;   // Tapers down to ~2.55mm at the tip for effortless insertion
    
    handle_d = 12;
    handle_thickness = 4;
    
    // 1. Teardrop Profile Drafting Function
    module teardrop_profile(w, h) {
        // Centered perfectly so scaling shrinks uniformly toward the core axis
        translate([0, -h/2]) { 
            hull() {
                translate([0, w/2]) circle(d=w, $fn=30); 
                translate([-w/2, h - w]) square([w, 0.1]); 
                translate([0, h]) polygon([[-0.1, 0], [0.1, 0], [0, 0.1]]); 
            }
        }
    }
    
    // 2. Upgraded Ribbed Grip Handle
    difference() {
        union() {
            cylinder(d=handle_d, h=handle_thickness, $fn=60);
            // 12 Tactile grip ribs around the outer perimeter
            for(i = [0 : 30 : 330]) {
                rotate([0, 0, i]) 
                    translate([handle_d/2, 0, 0]) 
                    cylinder(r=0.8, h=handle_thickness, $fn=16);
            }
        }
        // Easy-grip hollow underneath for fingertips
        translate([0, 0, -1]) cylinder(d=handle_d * 0.65, h=2, $fn=60); 
    }

    // 3. Reinforced Shaft Construction
    translate([0, 0, handle_thickness]) {
        
        // A. Structural Root Fillet (Prevents snapping at the layer lines)
        hull() {
            linear_extrude(0.1) teardrop_profile(base_w + 1.0, base_h + 1.0);
            translate([0, 0, 0.8]) linear_extrude(0.1) teardrop_profile(base_w, base_h);
        }
        
        // B. Main Tapered Friction Shaft
        translate([0, 0, 0.8]) {
            linear_extrude(height=shaft_length - 0.8, scale=tip_scale) {
                teardrop_profile(base_w, base_h);
            }
        }
    }
}
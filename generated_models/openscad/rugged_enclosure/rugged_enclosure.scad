// --- Configuration ---

// OPTIONS: "both", "body", "lid", "latch", "assembly"
part_to_show = "assembly"; 
explode_distance = 60; 

// -- Dimensions --
inner_length_x = 160; 
inner_width_y = 100;   
inner_height_z = 62; 
wall_thickness = 4;
corner_radius = 4;   

// -- M2 Hardware Specifics (EXACT) --
bolt_dia_clearance = 2.2;    
nut_flat_size = 4.6;         
nut_thickness = 2.0;         
bolt_head_dia = 4.2;         
bolt_head_depth = 2.5;       

// -- Width Calculations (EXACT 30mm Total) --
mount_thickness = 4;
latch_width = 22.0;          
hinge_width = 16.0;          

// -- Latch Geometry Settings --
latch_throw = 16.0; 
bolt_clearance = bolt_dia_clearance; 

// -- Mount Settings --
hole_offset_from_wall = 6.5; 
// Pivot point relative to the seam (Z=0 for lid, Z=split_height for body)
// Body Mount Pivot: 8mm below seam
latch_body_pivot_z = -8.0; 

// -- Hinge Settings --
hinge_offset = 5.4;     
hinge_knuckle_dia = 10;
hinge_pin_dia = bolt_dia_clearance;

// -- Other Settings --
split_height = 50;   
rib_width = 4;       
rib_depth = 2.5;     
rib_spacing = 20; 
oring_width = 1.8;
oring_depth = 2.0;
inlet_dia = 14;
inlet_z_center = 32;
inlet_x_from_front = 43;
outlet_dia = 20;
outlet_z_center = inlet_z_center;
outlet_x_from_front = inlet_x_from_front;
wire_dia = 4;
wire_z_pos = split_height - 20;
hardware_margin_ratio = 0.15;
$fn = 60;
epsilon = 0.1; 

// --- Calculated Dimensions ---
outer_x = inner_length_x + (wall_thickness * 2);
outer_y = inner_width_y + (wall_thickness * 2);
outer_z = inner_height_z + (wall_thickness * 2);

inner_corner_radius = max(wall_thickness / 2.0, corner_radius - wall_thickness);

pos_1_x = outer_x * hardware_margin_ratio;
pos_2_x = outer_x * (1.0 - hardware_margin_ratio);


// --- 1. LATCH DESIGN ---

module latch_2d_profile() {
    union() {
        difference() {
            union() {
                translate([0, latch_throw]) circle(d=10);
                circle(d=12); 
                hull() {
                    translate([0, latch_throw]) circle(d=10);
                    circle(d=10);
                }
            }
            union() {
                translate([0, latch_throw]) circle(d=bolt_clearance);
                circle(d=5); 
                rotate([0, 0, 170]) translate([0, -1]) square([10, 3]);
            }
        }
        rotate([0, 0, 5]) { 
            hull() {
                translate([0, -5]) square([6, 2], center=true);
                translate([0, -10]) circle(d=4);
            }
        }
    }
}

module rugged_latch() {
    width = latch_width - 0.4; 
    linear_extrude(height = width, center = true)
    latch_2d_profile();
}


// --- 2. MOUNTING SYSTEM (Secure Bell Profile) ---

// Creates a "Bell" profile: A cylinder that hullls back to a TALLER base on the wall.
// By making the base tall, the sides slope at ~35 degrees (support free).
// Clipping ensures the top/bottom are flat where needed.
module bell_mount_raw() {
    slope_angle = 35; 
    // Calculate required base height to achieve slope
    // dy = hole_offset_from_wall (6.5)
    // dz = dy * tan(angle)
    added_height = hole_offset_from_wall * tan(slope_angle); 
    base_h = 10 + (added_height * 2); // Cylinder dia + slope up + slope down

    hull() {
        // 1. Pivot Cylinder
        translate([0, -hole_offset_from_wall, 0]) 
            rotate([0, 90, 0]) 
            cylinder(h=mount_thickness, d=10, center=true);
        
        // 2. Wall Base (Wide and Tall)
        translate([0, 0, 0]) 
            cube([mount_thickness, 0.1, base_h], center=true);
    }
}

module latch_mounts_pair_body() {
    w_offset = (latch_width + mount_thickness) / 2; 
    trap_depth = 2.0; 
    
    // We clip the top of the body mount so it is flat at the split line
    // Body mount is at `split_height - 8`. We cut anything above `split_height`.
    // Local Z=0 is the pivot (-8 from split). Split is at Z=+8 locally.
    
    module body_mount_clipped() {
        intersection() {
            bell_mount_raw();
            // Bounding box: Everything below Z=+8 (relative to pivot)
            translate([0, -20, -50 + 8]) cube([50, 50, 100], center=true);
        }
    }

    // Left Mount (Bolt Head)
    translate([-w_offset, 0, 0]) 
    difference() {
        body_mount_clipped();
        translate([0, -hole_offset_from_wall, 0]) rotate([0, 90, 0]) cylinder(h=10, d=bolt_dia_clearance, center=true);
        translate([-mount_thickness/2 + trap_depth/2 - 0.01, -hole_offset_from_wall, 0]) 
            rotate([0, 90, 0]) cylinder(h=trap_depth, d=bolt_head_dia, center=true);
    }

    // Right Mount (Nut)
    translate([w_offset, 0, 0]) 
    difference() {
        body_mount_clipped();
        translate([0, -hole_offset_from_wall, 0]) rotate([0, 90, 0]) cylinder(h=10, d=bolt_dia_clearance, center=true);
        translate([mount_thickness/2 - trap_depth/2 + 0.01, -hole_offset_from_wall, 0]) 
            rotate([0, 90, 0]) rotate([0,0,30]) cylinder(h=trap_depth, d=nut_flat_size / cos(30), $fn=6, center=true);
    }
}

module latch_mounts_pair_lid() {
    w_offset = (latch_width + mount_thickness) / 2; 
    trap_depth = 2.0; 
    
    // We clip the BOTTOM of the lid mount so it is flat at the rim
    // Lid Pivot is at `split + pivot_z + throw`.
    // Seam is at `split`. 
    // Relative to pivot, seam is at `-(pivot_z + throw)`.
    // pivot_z = -8, throw = 12. Lid pivot relative to seam is -8 + 12 = +4.
    // So seam is at Z = -4 relative to lid pivot.
    
    dist_to_seam = -(latch_body_pivot_z + latch_throw); // e.g. -(-8 + 12) = -4
    
    module lid_mount_clipped() {
        intersection() {
            bell_mount_raw();
            // Bounding box: Everything ABOVE Z=-4
            translate([0, -20, 50 + dist_to_seam]) cube([50, 50, 100], center=true);
        }
    }
    
    // Left Mount (Bolt Head)
    translate([-w_offset, 0, 0]) 
    difference() {
        lid_mount_clipped();
        translate([0, -hole_offset_from_wall, 0]) rotate([0, 90, 0]) cylinder(h=10, d=bolt_dia_clearance, center=true);
        translate([-mount_thickness/2 + trap_depth/2 - 0.01, -hole_offset_from_wall, 0]) 
            rotate([0, 90, 0]) cylinder(h=trap_depth, d=bolt_head_dia, center=true);
    }

    // Right Mount (Nut)
    translate([w_offset, 0, 0]) 
    difference() {
        lid_mount_clipped();
        translate([0, -hole_offset_from_wall, 0]) rotate([0, 90, 0]) cylinder(h=10, d=bolt_dia_clearance, center=true);
        translate([mount_thickness/2 - trap_depth/2 + 0.01, -hole_offset_from_wall, 0]) 
            rotate([0, 90, 0]) rotate([0,0,30]) cylinder(h=trap_depth, d=nut_flat_size / cos(30), $fn=6, center=true);
    }
}


// --- 3. MAIN BOX COMPONENTS ---

module main_body_shell() {
    difference() {
        union() {
            rounded_cup(outer_x, outer_y, split_height, corner_radius);
            intersection() {
                rugged_ribs_smart(split_height - 2);
                translate([-2, -2, -2]) rounded_cup(outer_x+4, outer_y+4, split_height+2, corner_radius+2);
            }
            // Body Mounts
            translate([pos_1_x, 0, split_height + latch_body_pivot_z]) latch_mounts_pair_body();
            translate([pos_2_x, 0, split_height + latch_body_pivot_z]) latch_mounts_pair_body();
            
            // HINGES (Outer)
            translate([pos_1_x - (hinge_width/2), outer_y - 0.5, split_height - 15]) 
                hinge_knuckle_body_with_trap(trap_type="head", flip=true);
            translate([pos_2_x + (hinge_width/2), outer_y - 0.5, split_height - 15]) 
                hinge_knuckle_body_with_trap(trap_type="head", flip=false);
        }
        
        translate([wall_thickness, wall_thickness, wall_thickness])
             rounded_cup(inner_length_x, inner_width_y, split_height + epsilon, inner_corner_radius);
        
        translate([wall_thickness/2, wall_thickness/2, split_height - oring_depth])
            linear_extrude(height = oring_depth + epsilon)
            difference() {
                offset(r = oring_width/2) rounded_profile(inner_length_x + wall_thickness, inner_width_y + wall_thickness, corner_radius);
                offset(r = -oring_width/2) rounded_profile(inner_length_x + wall_thickness, inner_width_y + wall_thickness, corner_radius);
            }
            
        translate([wall_thickness + inlet_x_from_front, -5, inlet_z_center]) rotate([-90, 0, 0]) cylinder(h=wall_thickness + 10, d=inlet_dia); 
        translate([wall_thickness + outlet_x_from_front, outer_y - wall_thickness - 5, outlet_z_center]) rotate([-90, 0, 0]) cylinder(h=wall_thickness + 10, d=outlet_dia); 
        
        translate([outer_x/2, outer_y, wire_z_pos]) rotate([90, 0, 0]) cylinder(h=20, d=wire_dia, center=true); 
    }
}

module lid_shell() {
    lid_h = outer_z - split_height;
    safe_h = max(lid_h, wall_thickness + 1);

    difference() {
        union() {
            rounded_cap(outer_x, outer_y, safe_h, corner_radius);
            intersection() {
                translate([0,0,2]) rugged_ribs_smart(safe_h - 2);
                translate([-2, -2, 0]) rounded_cap(outer_x+4, outer_y+4, safe_h+2, corner_radius+2);
            }
            // Lid Mounts
            // Z = body_pivot + throw
            translate([pos_1_x, 0, latch_body_pivot_z + latch_throw]) latch_mounts_pair_lid();
            translate([pos_2_x, 0, latch_body_pivot_z + latch_throw]) latch_mounts_pair_lid();
            
            // HINGES (Inner)
            translate([pos_1_x + (hinge_width/2), outer_y - 0.5, 0]) 
                hinge_knuckle_lid_with_trap(trap_type="nut", flip=false);
            translate([pos_2_x - (hinge_width/2), outer_y - 0.5, 0]) 
                hinge_knuckle_lid_with_trap(trap_type="nut", flip=true);
        }

        translate([wall_thickness, wall_thickness, -epsilon])
             rounded_cap(inner_length_x, inner_width_y, safe_h - wall_thickness + epsilon, inner_corner_radius);
    }
    
    translate([wall_thickness/2, wall_thickness/2, 0])
            linear_extrude(height = 1.0)
            difference() {
                offset(r = (oring_width/2) - 0.2) rounded_profile(inner_length_x + wall_thickness, inner_width_y + wall_thickness, corner_radius);
                offset(r = -(oring_width/2) + 0.2) rounded_profile(inner_length_x + wall_thickness, inner_width_y + wall_thickness, corner_radius);
            }
}


// --- HELPER MODULES ---

module rounded_cup(x, y, h, r) {
    safe_r = max(r, 0.1);
    hull() {
        translate([safe_r, safe_r, safe_r]) sphere(r=safe_r);
        translate([x-safe_r, safe_r, safe_r]) sphere(r=safe_r);
        translate([x-safe_r, y-safe_r, safe_r]) sphere(r=safe_r);
        translate([safe_r, y-safe_r, safe_r]) sphere(r=safe_r);
        
        translate([safe_r, safe_r, h-0.1]) cylinder(h=0.1, r=safe_r);
        translate([x-safe_r, safe_r, h-0.1]) cylinder(h=0.1, r=safe_r);
        translate([x-safe_r, y-safe_r, h-0.1]) cylinder(h=0.1, r=safe_r);
        translate([safe_r, y-safe_r, h-0.1]) cylinder(h=0.1, r=safe_r);
    }
}

module rounded_cap(x, y, h, r) {
    safe_r = max(r, 0.1);
    safe_h = max(h, safe_r + 0.1); 
    hull() {
        translate([safe_r, safe_r, 0]) cylinder(h=0.1, r=safe_r);
        translate([x-safe_r, safe_r, 0]) cylinder(h=0.1, r=safe_r);
        translate([x-safe_r, y-safe_r, 0]) cylinder(h=0.1, r=safe_r);
        translate([safe_r, y-safe_r, 0]) cylinder(h=0.1, r=safe_r);
        
        translate([safe_r, safe_r, safe_h-safe_r]) sphere(r=safe_r);
        translate([x-safe_r, safe_r, safe_h-safe_r]) sphere(r=safe_r);
        translate([x-safe_r, y-safe_r, safe_h-safe_r]) sphere(r=safe_r);
        translate([safe_r, y-safe_r, safe_h-safe_r]) sphere(r=safe_r);
    }
}

module rounded_profile(x, y, r) {
    safe_r = max(r, 0.1);
    hull() {
        translate([safe_r, safe_r]) circle(r=safe_r);
        translate([x-safe_r, safe_r]) circle(r=safe_r);
        translate([x-safe_r, y-safe_r]) circle(r=safe_r);
        translate([safe_r, y-safe_r]) circle(r=safe_r);
    }
}

module rugged_ribs_smart(height) {
    avoid_zone = (latch_width/2) + mount_thickness + 4; 
    x_len = outer_x - (corner_radius*4);
    count_x = x_len > 0 ? floor(x_len / rib_spacing) : 0;
    
    if (count_x > 0) {
        step_x = x_len / (count_x + 1);
        for (i = [1:count_x]) {
            x_pos = (corner_radius*2) + (i * step_x);
            if (abs(x_pos - pos_1_x) > avoid_zone && abs(x_pos - pos_2_x) > avoid_zone) {
                translate([x_pos - (rib_width/2), -rib_depth, 0]) cube([rib_width, outer_y + (rib_depth*2), height]);
            }
        }
    }
    
    y_len = outer_y - (corner_radius*4);
    count_y = y_len > 0 ? floor(y_len / rib_spacing) : 0;
    
    if (count_y > 0) {
        step_y = y_len / (count_y + 1);
        for (j = [1:count_y]) {
            y_pos = (corner_radius*2) + (j * step_y);
            translate([-rib_depth, y_pos - (rib_width/2), 0]) cube([outer_x + (rib_depth*2), rib_width, height]);
        }
    }
}

module hinge_knuckle_body_with_trap(trap_type="none", flip=false) {
    trap_offset = (hinge_width/2) - (bolt_head_depth/2) + 0.1;
    difference() {
        hinge_knuckle_body();
        translate([0, hinge_offset, 15]) 
        rotate([0, 90, 0]) 
        if (trap_type == "head") {
             translate([0, 0, flip ? -trap_offset : trap_offset]) 
             cylinder(h=bolt_head_depth + 1, d=bolt_head_dia, center=true);
        } else if (trap_type == "nut") {
             translate([0, 0, flip ? -trap_offset : trap_offset]) 
             rotate([0, 0, 30]) cylinder(h=nut_thickness + 1, d=nut_flat_size / cos(30), $fn=6, center=true);
        }
    }
}

module hinge_knuckle_lid_with_trap(trap_type="none", flip=false) {
    trap_offset = (hinge_width/2) - (nut_thickness/2) + 0.1;
    difference() {
        hinge_knuckle_lid();
        translate([0, hinge_offset, 0]) 
        rotate([0, 90, 0]) 
        if (trap_type == "head") {
             translate([0, 0, flip ? -trap_offset : trap_offset]) 
             cylinder(h=bolt_head_depth + 1, d=bolt_head_dia, center=true);
        } else if (trap_type == "nut") {
             translate([0, 0, flip ? -trap_offset : trap_offset]) 
             rotate([0, 0, 30]) cylinder(h=nut_thickness + 1, d=nut_flat_size / cos(30), $fn=6, center=true);
        }
    }
}

module hinge_knuckle_body() {
    difference() {
        hull() {
            translate([0, hinge_offset, 15]) rotate([0,90,0]) cylinder(h=hinge_width, d=hinge_knuckle_dia, center=true);
            translate([-hinge_width/2, 0, 0]) cube([hinge_width, 0.1, 15]); 
        }
        translate([0, hinge_offset, 15]) rotate([0,90,0]) cylinder(h=hinge_width+2, d=hinge_pin_dia, center=true);
    }
}

module hinge_knuckle_lid() {
    difference() {
        hull() {
            translate([0, hinge_offset, 0]) rotate([0,90,0]) cylinder(h=hinge_width, d=hinge_knuckle_dia, center=true);
            translate([-hinge_width/2, 0, 0]) cube([hinge_width, 0.1, 12]);
        }
        translate([0, hinge_offset, 0]) rotate([0,90,0]) cylinder(h=hinge_width+2, d=hinge_pin_dia, center=true);
    }
}

// --- RENDER LOGIC ---

if (part_to_show == "body") {
    main_body_shell();
} else if (part_to_show == "lid") {
    translate([0, outer_y + 20, 0]) lid_shell();
} else if (part_to_show == "latch") {
    rugged_latch();
} else if (part_to_show == "assembly") {
    main_body_shell();
    translate([0, 0, split_height + explode_distance]) lid_shell();
    
    color("orange") {
        z_pivot = split_height + explode_distance + latch_body_pivot_z + latch_throw;
        
        translate([pos_1_x, -hole_offset_from_wall, z_pivot]) 
            rotate([0, 90, 0])  
            rotate([0, 0, 180]) 
            rotate([180, 0, 0]) 
            translate([0, -latch_throw, 0]) 
            rugged_latch();
            
        translate([pos_2_x, -hole_offset_from_wall, z_pivot]) 
            rotate([0, 90, 0])  
            rotate([0, 0, 180])
            rotate([180, 0, 0])
            translate([0, -latch_throw, 0]) 
            rugged_latch();
    }
}
// ==========================================
// Stepped & Flared Snap-Fit C-Clamp Hanger
// ==========================================
$fn = 60; // Smooth curves

/* [Print Options] */
// Which side of the door do you want to print?
render_part = "Both"; // ["Both", "Right", "Left"]

/* [Door Jamb & Trim Dimensions] */
// Width of the flat inner door frame (the jamb)
jamb_width = 128; 

// The flat gap along the wall BEFORE the trim sticks out
trim_step_x = 10; 

// How far the trim edge sticks out from the wall at the step
trim_step_y = 10; 

// How far the clamp legs reach along the wall over the trim
trim_reach = 73; 

// How much the trim flares OUTWARDS on each side
trim_flare = 15; 

/* [Door Stop Molding Cutout] */
// Width of the raised wood strip in the middle of the frame
stop_width = 38; 

// How far it sticks out into the doorway
stop_depth = 12; 

// EXPLICIT CONTROL: Distance from front edge to the bump on the LEFT side
stop_offset_left = 36; 

// EXPLICIT CONTROL: Distance from front edge to the bump on the RIGHT side
stop_offset_right = 47; 

/* [Rod & Holder Dimensions] */
// Outer diameter of your horizontal bar (1/2" PVC is ~21.5mm)
rod_od = 22; 

// Extra clearance so the rod drops in easily
rod_clearance = 3; 

// How far the holder sticks out into the doorway opening
saddle_extension = 30; 

/* [Clamp & Hook Properties] */
// Thickness of the plastic walls (Recommended 4mm-5mm for strength)
t = 5; 

// Vertical height of the bracket (Thickness resting on the print bed)
h = 40; 

// How thick the hook block is along the outer wall (provides strength)
hook_length = 6; 

/* [Rounding & Gripping Options] */
// Radius of the outer rounded corners
corner_radius = 2.0; 

// Toggle: Make the inner catching face of the hook razor-sharp? 
sharp_catch = true; 


// ==========================================
// Derived Variables (Globals)
// ==========================================
rod_d = rod_od + rod_clearance;
saddle_width = rod_d + 2*t;
saddle_x = t + stop_depth; 
rod_z = t + rod_d/2; 
safe_r = min(corner_radius, 1.8); 


// ==========================================
// Print Platter Layout
// ==========================================

if (render_part == "Both" || render_part == "Left") {
    // --- LEFT PART ---
    door_hanger(local_stop_offset = stop_offset_left);
}

if (render_part == "Both" || render_part == "Right") {
    // --- RIGHT PART ---
    // Shift it over so they don't overlap on the build plate
    shift_x = (render_part == "Both") ? (trim_reach * 2 + 30) : 0;
    
    translate([shift_x, 0, 0]) 
        door_hanger(local_stop_offset = stop_offset_right);
}


// ==========================================
// Modules
// ==========================================

module base_profile(local_stop_offset) {
    local_saddle_y_center = local_stop_offset + (stop_width / 2);

    pts = concat(
        [
            [-trim_reach - hook_length, -trim_flare - t],            
            [-trim_reach, -trim_flare - t],                           
            [-trim_step_x + t, -trim_step_y - t],      
            [-trim_step_x + t, -t],                    
            [t, -t]
        ],
        (stop_depth > 0) ? [
            [t, local_stop_offset - t],
            [t + stop_depth, local_stop_offset - t],
            [t + stop_depth, local_stop_offset + stop_width + t],
            [t, local_stop_offset + stop_width + t]
        ] : [],
        [
            [t, jamb_width + t],                                
            [-trim_step_x + t, jamb_width + t],        
            [-trim_step_x + t, jamb_width + trim_step_y + t], 
            [-trim_reach, jamb_width + trim_flare + t],               
            [-trim_reach - hook_length, jamb_width + trim_flare + t], 
            
            [-trim_reach - hook_length, jamb_width],                  
            [-trim_reach, jamb_width],                                
            [-trim_reach, jamb_width + trim_flare],                   
            [-trim_step_x, jamb_width + trim_step_y],                 
            [-trim_step_x, jamb_width],                               
            [0, jamb_width]
        ],
        (stop_depth > 0) ? [
            [0, local_stop_offset + stop_width],
            [stop_depth, local_stop_offset + stop_width],
            [stop_depth, local_stop_offset],
            [0, local_stop_offset]
        ] : [],
        [
            [0, 0],                                                   
            [-trim_step_x, 0],                                        
            [-trim_step_x, -trim_step_y],                             
            [-trim_reach, -trim_flare],                               
            [-trim_reach, 0],                                         
            [-trim_reach - hook_length, 0]                            
        ]
    );

    union() {
        polygon(pts);
        translate([saddle_x - 0.1, local_saddle_y_center - saddle_width/2 ])
            square([saddle_extension + 0.1, saddle_width]);
    }
}

module final_2d(local_stop_offset) {
    union() {
        offset(r = safe_r) 
        offset(r = -2 * safe_r) 
        offset(r = safe_r) 
        base_profile(local_stop_offset);
        
        if (sharp_catch) {
            translate([-trim_reach - hook_length, -safe_r])
                square([hook_length, safe_r]);
                
            translate([-trim_reach - hook_length, jamb_width])
                square([hook_length, safe_r]);
        }
    }
}

module door_hanger(local_stop_offset) {
    local_saddle_y_center = local_stop_offset + (stop_width / 2);

    difference() {
        linear_extrude(height = h) {
            final_2d(local_stop_offset);
        }
        
        translate([saddle_x - 1, local_saddle_y_center, rod_z])
            rotate([0, 90, 0])
            cylinder(d=rod_d, h=saddle_extension + 2);
            
        translate([saddle_x - 1, local_saddle_y_center - rod_d/2, rod_z])
            cube([saddle_extension + 2, rod_d, h]);
            
        difference() {
            translate([saddle_x - 0.01, local_saddle_y_center - saddle_width/2 - 1, -1])
                cube([saddle_extension + 2, saddle_width + 2, rod_z + 1]);
                
            union() {
                translate([saddle_x - 1, local_saddle_y_center, rod_z])
                    rotate([0, 90, 0])
                    cylinder(d=saddle_width, h=saddle_extension + 4);
                    
                hull() {
                    translate([saddle_x - 0.1, local_saddle_y_center - saddle_width/2, 0])
                        cube([0.2, saddle_width, rod_z]);
                        
                    translate([saddle_x + 15, local_saddle_y_center, rod_z])
                        rotate([0, 90, 0])
                        cylinder(d=saddle_width, h=0.2);
                }
            }
        }
    }
}
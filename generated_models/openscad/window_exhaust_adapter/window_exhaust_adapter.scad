// --- Print Selection ---
// 0 = View Both (Preview only)
// 1 = Left Side (Male)
// 2 = Right Side (Female)
print_selection = 0;

// --- Dimensions (in mm) ---
total_length = 340; 
total_height = 40;
total_width  = 37;

// Grooves
bottom_groove_width = 12; 
bottom_groove_depth = 2;

top_groove_width = 13;
top_groove_depth = 20;

// --- Relief (Widening the Slit) ---
// This widens the groove at the very ends to fit the L-shape
relief_length = 30;      // How far into the bar the wider section goes
relief_widen_by = 1;    // How much wider to make the slit (2mm)
relief_on_top = true;   // Apply to the Top Groove (Exhaust Panel)?
relief_on_bottom = false; // Apply to the Bottom Groove (Window Track)?

// Dovetail Tolerance
joint_tolerance = 0.15;

// --- Main Logic ---

module full_bar() {
    difference() {
        // 1. Main Block
        translate([-total_length/2, -total_width/2, 0])
        cube([total_length, total_width, total_height]);

        // 2. Bottom Groove
        translate([-total_length/2 - 1, -bottom_groove_width/2, -0.1])
        cube([total_length + 2, bottom_groove_width, bottom_groove_depth + 0.1]);

        // 3. Top Groove
        translate([-total_length/2 - 1, -top_groove_width/2, total_height - top_groove_depth])
        cube([total_length + 2, top_groove_width, top_groove_depth + 0.1]);

        // 4. Relief Cuts (Widening the Slit at Ends)
        
        // --- TOP GROOVE RELIEFS ---
        if (relief_on_top) {
            // Cut "Left" End (widens the -Y side of the groove)
            translate([-total_length/2 - 0.1, -top_groove_width/2 - relief_widen_by, total_height - top_groove_depth])
            cube([relief_length + 0.1, relief_widen_by, top_groove_depth + 0.1]);

            // Cut "Right" End (widens the -Y side of the groove)
            translate([total_length/2 - relief_length, -top_groove_width/2 - relief_widen_by, total_height - top_groove_depth])
            cube([relief_length + 0.1, relief_widen_by, top_groove_depth + 0.1]);
        }

        // --- BOTTOM GROOVE RELIEFS (Optional) ---
        if (relief_on_bottom) {
            translate([-total_length/2 - 0.1, -bottom_groove_width/2 - relief_widen_by, -0.1])
            cube([relief_length + 0.1, relief_widen_by, bottom_groove_depth + 0.2]);

            translate([total_length/2 - relief_length, -bottom_groove_width/2 - relief_widen_by, -0.1])
            cube([relief_length + 0.1, relief_widen_by, bottom_groove_depth + 0.2]);
        }
    }
}

module dovetail_shape(offset_val) {
    wedge_len = 15;
    wedge_max_width = 18;
    wedge_min_width = 10;
    
    linear_extrude(height=total_height+1, center=false)
    polygon(points=[
        [0, -wedge_min_width/2 + offset_val],
        [wedge_len, -wedge_max_width/2 + offset_val],
        [wedge_len, wedge_max_width/2 - offset_val],
        [0, wedge_min_width/2 - offset_val]
    ]);
}

module cutter_mask(is_hole) {
    offset_val = is_hole ? joint_tolerance : 0;
    
    union() {
        translate([-total_length, -total_width, -1])
        cube([total_length, total_width*2, total_height+2]);
        
        translate([0,0,-1])
        dovetail_shape(is_hole ? -joint_tolerance : 0);
    }
}

// --- Rendering ---
if (print_selection == 0) {
    color("Cyan") intersection() { full_bar(); cutter_mask(false); }
    color("Yellow") translate([5, 0, 0]) difference() { full_bar(); cutter_mask(true); }
} else if (print_selection == 1) {
    intersection() { full_bar(); cutter_mask(false); }
} else if (print_selection == 2) {
    difference() { full_bar(); cutter_mask(true); }
}

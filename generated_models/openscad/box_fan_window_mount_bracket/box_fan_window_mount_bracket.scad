// ==========================================
// OVERALL DIMENSIONS & PARAMETERS
// ==========================================
// Distance between the inner faces of the downward hooks (Adjust based on your fan!)
fan_thickness = 105.6;  
bar_width = 8.0;        // Width of the main straight spine
hook_thickness = 6.0;   // Thickness of the arms that drop down to grab the fan
hook_drop = 26.0;       // How far down the arms reach

// Pincer/Lip Lengths (Horizontal parts that grab the fan)
left_pincer_length = 12.0;   // Shorter side with no teeth.
right_pincer_length = 14.0;  // This is the side with teeth.

// Window Mounting Parameters
window_track_width = 37.0;  // FIXED: Changed to 37.0 to match the physical reality of your window!
block_tolerance = 1.0;      // Clearance on each side of the solid block (2mm total clearance)
block_offset = 0.0;         // EXACT distance from the right edge to the mounting feature

// Auto-calculated overall length so you don't have to guess
overall_length = fan_thickness + (2 * hook_thickness);

// ==========================================
// TEETH PARAMETERS (Z-Axis alternating)
// ==========================================
tooth_width = 9.8;      // Thickness of each tooth in the Z-axis
tooth_gap = 2.0;        // Gap between the teeth in the Z-axis
num_teeth = 2;          // SET TO 2 (Change this to auto-scale the whole part!)

// How far the teeth stick out from the tip of the pincer (X-axis direction)
tooth_extension = 5.0;  

// Automatically calculate the required Z-axis thickness of the entire part
part_thickness = (tooth_width * num_teeth) + (tooth_gap * (num_teeth - 1));

// Corner rounding radius (Increase this to make corners softer)
corner_radius = 1.5;

// Smoothness for the rounded corners
$fn = 60; 

// ==========================================
// MAGIC ROUNDING MODULE
// ==========================================
module round_all_corners(r) {
    offset(r = -r) offset(r = 2*r) offset(r = -r) children();
}

// ==========================================
// 2D BASE PROFILE 
// ==========================================
module bracket_2d_profile(include_block = false) {
    round_all_corners(corner_radius) {
        union() {
            // Main long spine
            square([overall_length, bar_width]);
            
            // --- LEFT HOOK ---
            // The vertical drop
            translate([0, -hook_drop]) square([hook_thickness, hook_drop]);
            // Inner hook lip (pointing right)
            translate([0, -hook_drop]) square([left_pincer_length, hook_thickness]);
            
            // Extra corner support (Made perfectly flush with the left edge to prevent bulging)
            translate([-3, -bar_width]) square([hook_thickness , 16]); 
            
            // --- RIGHT HOOK ---
            // The vertical drop
            translate([overall_length - hook_thickness, -hook_drop]) square([hook_thickness, hook_drop]);
            // Inner hook lip (pointing left)
            translate([overall_length - right_pincer_length, -hook_drop]) square([right_pincer_length, hook_thickness]);
            
            // Extra corner support (Made perfectly flush with the right edge to prevent bumping the window!)
            translate([overall_length - hook_thickness , -bar_width]) square([hook_thickness + 3, 16]);
            
            // --- MOUNTING BRACKETS (Top side) ---
            
            // We strictly align the right-most edge of BOTH features (the right brace or the block) 
            // so they start exactly `block_offset` from the extreme right edge of the clamp.
            feature_right_x = overall_length - block_offset;
            
            if (include_block) {
                // Solid Block (Clamp 2)
                // Width is exactly the track width minus total tolerance (2mm)
                block_width = window_track_width - (2 * block_tolerance);
                
                // Position the block so its right edge touches exactly at feature_right_x
                translate([feature_right_x - block_width, bar_width]) 
                    square([block_width, 20]);
                    
            } else {
                // Two Braces (Clamp 1)
                // Position the right brace so its right edge touches exactly at feature_right_x
                right_brace_x = feature_right_x - bar_width;
                
                // Position the left brace so the inner gap is EXACTLY window_track_width
                left_brace_x = right_brace_x - window_track_width - bar_width;
                
                translate([left_brace_x, bar_width]) square([bar_width, 20]);
                translate([right_brace_x, bar_width]) square([bar_width, 20]);
            }
        }
    }
}

// ==========================================
// 3D TEETH GENERATOR (WITH ROUNDED EDGES)
// ==========================================

// Create a 2D rounded tooth profile
module rounded_tooth_2d() {
    round_all_corners(corner_radius) {
        // We extend the base backwards by 2mm (X=-2) so it sinks deeply 
        // and seamlessly into the main bracket without leaving a weak seam
        translate([-2, 0])
            square([tooth_extension + 2, hook_thickness]);
    }
}

module teeth_array() {
    // Generate the teeth stacking up along the Z-axis
    for (i = [0 : num_teeth - 1]) {
        // Calculate the starting Z height for each tooth
        z_pos = i * (tooth_width + tooth_gap);
        
        // Right Pincer Teeth (Mirrored to point the opposite way)
        // Automatically follows the right pincer variable
        translate([overall_length - right_pincer_length, -hook_drop, z_pos])
            linear_extrude(height = tooth_width)
                mirror([1, 0, 0]) // Flip the tooth so it points left
                    rounded_tooth_2d();
    }
}

// ==========================================
// FINAL 3D ASSEMBLY
// ==========================================
module final_bracket(include_block) {
    union() {
        // 1. Extrude the base bracket to the auto-calculated thickness
        linear_extrude(height = part_thickness)
            bracket_2d_profile(include_block);
            
        // 2. Attach the rounded 3D teeth arrays to the tips of the hooks
        teeth_array();
    }
}

// ==========================================
// DISPLAY RENDER
// ==========================================

// Part 1: Top Bracket (WITH the solid block)
translate([0, 60, 0]) 
    final_bracket(include_block = true);

// Part 2: Bottom Bracket (CLEAN, no block)
final_bracket(include_block = false);
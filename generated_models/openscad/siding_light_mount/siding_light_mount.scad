// Angled Siding Mount Compensator - Offset V-Tracks

/* [Light Dimensions] */
// Total height of the light fixture base (mm)
light_height = 180;
// Total width of the light fixture base (mm)
light_width = 112;

/* [Mount Aesthetics & Clearances] */
// How much wider/taller the mount is than the light (mm per side)
plate_margin = 20; 
// Width of the inner hollow cutout (mm)
opening_width = 100;
// Bottom solid border thickness (mm)
bottom_border = 20;
// Top solid border thickness (mm)
top_border = 20;

/* [Light Mounting Bracket (The Bridge)] */
// Distance from the BOTTOM of the LAMP to the center of the bracket hole (mm)
lamp_mount_center = 106;
// Total height of the solid mounting bridge (mm)
bridge_height = 60;
// Diameter of the central clearance hole (mm)
center_hole_dia = 40;
// Length of the angled screw slots for adjustability (mm)
slot_length = 26;
// Width of the screw tracks (4.5mm perfectly fits standard #8 or M4 fixture bolts)
bracket_slot_width = 4.5;
// Horizontal distance from center line where the tracks START (mm)
slot_start_dist = 22; 
// Vertical distance ABOVE the center line where the tracks START (mm)
slot_start_y_offset = 15;
// Solid thickness of the bridge where the bracket mounts (mm)
bridge_thickness = 8;
// Width of the recessed track on the back for the hex nut (mm)
nut_recess_width = 10; 

/* [Siding Profile] */
// The horizontal "step" depth of the siding board (mm)
siding_rise = 17;   
// The vertical exposed length of the siding board (mm)
siding_run = 175;   

/* [Wall Mounting Screws (Hidden in corners)] */
screw_hole_dia = 4.5;
screw_head_dia = 9.0;
screw_head_depth = 3.0;
tab_width = 15;
tab_height = 25;

/* [Mount Settings] */
// Minimum thickness of the mount at the thinnest point (bottom)
min_thickness = 5;  

/* [Calculated Values] */
// Total dimensions of the 3D printed plate
mount_height = light_height + (plate_margin * 2); // 220 mm
mount_width = light_width + (plate_margin * 2);   // 152 mm

// Center coordinates
center_z = mount_width / 2;
mount_center_y = lamp_mount_center + plate_margin;
bridge_top_y = mount_center_y + (bridge_height / 2);
bridge_bottom_y = mount_center_y - (bridge_height / 2);

// Slope of the siding
slope = siding_rise / siding_run;

// AUTO-CENTERING LOGIC
lap1_y = (mount_height - siding_run) / 2;
lap2_y = lap1_y + siding_run;

// Functions to calculate thickness at any Y coordinate
function t_b0(y) = min_thickness + (y - (lap1_y - siding_run)) * slope; 
function t_b1(y) = min_thickness + (y - lap1_y) * slope;                
function t_b2(y) = min_thickness + (y - lap2_y) * slope;                

module siding_mount() {
    
    // Assemble the polygon points for the sawtooth back
    p_base = [
        [0, 0],                               
        [t_b0(0), 0],                         
        [t_b0(lap1_y), lap1_y],               
        [t_b1(lap1_y), lap1_y]                
    ];
    
    p_lap2 = (lap2_y < mount_height) ? [
        [t_b1(lap2_y), lap2_y],               
        [t_b2(lap2_y), lap2_y],               
        [t_b2(mount_height), mount_height]    
    ] : [
        [t_b1(mount_height), mount_height]    
    ];
    
    p_top = [ [0, mount_height] ];
    poly_points = concat(p_base, p_lap2, p_top);

    difference() {
        // Main wedge body
        linear_extrude(height = mount_width, center=false) {
            polygon(points = poly_points);
        }
        
        side_border = (mount_width - opening_width) / 2;
        max_cut_depth = 80; 
        
        // --- HOLLOW REGIONS ---
        
        // 1. Lower Hollow 
        translate([-10, bottom_border + tab_height, side_border])
            cube([max_cut_depth, bridge_bottom_y - (bottom_border + tab_height), opening_width]);
            
        // 2. Bottom Tab Hollow 
        translate([-10, bottom_border, side_border + tab_width])
            cube([max_cut_depth, tab_height + 0.1, opening_width - (tab_width * 2)]);

        // 3. Upper Hollow 
        translate([-10, bridge_top_y, side_border])
            cube([max_cut_depth, mount_height - top_border - tab_height - bridge_top_y, opening_width]);
            
        // 4. Top Tab Hollow 
        translate([-10, mount_height - top_border - tab_height, side_border + tab_width])
            cube([max_cut_depth, tab_height + 0.1, opening_width - (tab_width * 2)]);

        // --- BRIDGE CUTOUTS ---

        // 5. Central clearance hole in the bridge
        translate([-10, mount_center_y, center_z])
            rotate([0, 90, 0])
            cylinder(h = max_cut_depth, d = center_hole_dia, $fn=60);

        // 6. Right mounting slot (Front side - Angled 30 degrees Up & Out)
        translate([-10, mount_center_y + slot_start_y_offset, center_z + slot_start_dist])
            rotate([30, 0, 0])
            translate([0, -bracket_slot_width / 2, 0])
            cube([max_cut_depth, bracket_slot_width, slot_length]);
            
        // 7. Left mounting slot (Front side - Mirrored to butterfly Up & Out)
        translate([-10, mount_center_y + slot_start_y_offset, center_z - slot_start_dist])
            mirror([0, 0, 1])
            rotate([30, 0, 0])
            translate([0, -bracket_slot_width / 2, 0])
            cube([max_cut_depth, bracket_slot_width, slot_length]);

        // 8. Right NUT RECESS (Back side)
        translate([bridge_thickness, mount_center_y + slot_start_y_offset, center_z + slot_start_dist])
            rotate([30, 0, 0])
            translate([0, -nut_recess_width / 2, -2]) // Starts slightly before 0 for clearance
            cube([max_cut_depth, nut_recess_width, slot_length + 4]);

        // 9. Left NUT RECESS (Back side)
        translate([bridge_thickness, mount_center_y + slot_start_y_offset, center_z - slot_start_dist])
            mirror([0, 0, 1])
            rotate([30, 0, 0])
            translate([0, -nut_recess_width / 2, -2]) // Starts slightly before 0 for clearance
            cube([max_cut_depth, nut_recess_width, slot_length + 4]);

        // --- CORNER MOUNTING SCREWS ---

        // 10. Left Bottom Corner Screw
        translate([0, bottom_border + (tab_height / 2), side_border + (tab_width / 2)])
            rotate([0, 90, 0]) {
                cylinder(h = max_cut_depth, d = screw_hole_dia, $fn=36);
                translate([0, 0, -0.01]) cylinder(h = screw_head_depth, d1 = screw_head_dia, d2 = screw_hole_dia, $fn=36);
                translate([0, 0, -5]) cylinder(h = 5, d = screw_head_dia, $fn=36);
            }

        // 11. Right Bottom Corner Screw
        translate([0, bottom_border + (tab_height / 2), mount_width - side_border - (tab_width / 2)])
            rotate([0, 90, 0]) {
                cylinder(h = max_cut_depth, d = screw_hole_dia, $fn=36);
                translate([0, 0, -0.01]) cylinder(h = screw_head_depth, d1 = screw_head_dia, d2 = screw_hole_dia, $fn=36);
                translate([0, 0, -5]) cylinder(h = 5, d = screw_head_dia, $fn=36);
            }
            
        // 12. Left Top Corner Screw
        translate([0, mount_height - top_border - (tab_height / 2), side_border + (tab_width / 2)])
            rotate([0, 90, 0]) {
                cylinder(h = max_cut_depth, d = screw_hole_dia, $fn=36);
                translate([0, 0, -0.01]) cylinder(h = screw_head_depth, d1 = screw_head_dia, d2 = screw_hole_dia, $fn=36);
                translate([0, 0, -5]) cylinder(h = 5, d = screw_head_dia, $fn=36);
            }

        // 13. Right Top Corner Screw
        translate([0, mount_height - top_border - (tab_height / 2), mount_width - side_border - (tab_width / 2)])
            rotate([0, 90, 0]) {
                cylinder(h = max_cut_depth, d = screw_hole_dia, $fn=36);
                translate([0, 0, -0.01]) cylinder(h = screw_head_depth, d1 = screw_head_dia, d2 = screw_hole_dia, $fn=36);
                translate([0, 0, -5]) cylinder(h = 5, d = screw_head_dia, $fn=36);
            }
    }
}

// Render the part
siding_mount();
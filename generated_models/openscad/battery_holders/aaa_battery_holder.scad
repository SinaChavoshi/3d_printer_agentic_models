// --- PARAMETERS ---
battery_diameter  = 10.6;  // AAA standard + 0.1mm tolerance
wall_min          = 1.0;   // Minimum distance between battery slots
plate_thickness   = 20.0;  // 2 cm thick plate
bottom_thickness  = 1.0;   // 2 mm solid bottom floor
cols              = 10;    // Number of columns
rows              = 5;    // Number of rows
corner_radius     = 1.0;   // External edge rounding radius
chamfer_radius    = 0.5;   // Top hole lip rounding/chamfer radius
// --- CALCULATIONS ---
hole_depth        = plate_thickness - bottom_thickness;  // Depth of the battery pocket
pitch         = battery_diameter + wall_min;
base_width    = (cols * pitch) + wall_min;
base_length   = (rows * pitch) + wall_min;

// --- MODULE ---
module battery_holder() {
    render()
    difference() {
        // Rounded external base using minkowski or linear_extrude with offset
        translate([corner_radius, corner_radius, 0])
        minkowski() {
            cube([base_width - (corner_radius * 2), base_length - (corner_radius * 2), plate_thickness - corner_radius]);
            sphere(r = corner_radius, $fn = 30);
        }
        
        // Subtract battery cavity grid with top chamfer
        for (c = [0 : cols - 1]) {
            for (r = [0 : rows - 1]) {
                bx = wall_min + c * pitch + battery_diameter / 2;
                by = wall_min + r * pitch + battery_diameter / 2;
                bz = bottom_thickness;
                
                translate([bx, by, bz]) {
                    // Main cylinder
                    cylinder(h = hole_depth + 1, d = battery_diameter, $fn = 50);
                    
                    // Top hole rounding/chamfer
                    translate([0, 0, hole_depth-1])
                    cylinder(h = chamfer_radius +1, r1 = battery_diameter / 2, r2 = (battery_diameter / 2) + chamfer_radius, $fn = 50);
                }
            }
        }
        
        // Trim the bottom flat since minkowski rounds the base downwards
        translate([-base_width, -base_length, -corner_radius * 2])
        cube([base_width * 3, base_length * 3, corner_radius * 2]);
        
        // Trim the top flat to maintain exact plate_thickness height
        translate([-base_width, -base_length, plate_thickness])
        cube([base_width * 3, base_length * 3, corner_radius * 2]);
    }
}

// Render the model
battery_holder();
// --- PARAMETERS ---
// Hexagon Slot Dimensions
slot_size = 25.0;       // Flat-to-flat inner width of a hex
slot_height = 25.0;     // Height of the main rectangular base
wall_protrusion = 4.0;  // How high the hex walls stick up above the base

// Layout Configuration
cols = 7;               // Number of columns
rows = 8;               // Number of staggered rows
wall_thickness = 2.0;   // Thickness of the honeycomb walls
base_thickness = 2.0;   // Solid floor thickness at the bottom

// Framing Parameter
edge_margin = 2.0;      // Flat perimeter space around the honeycomb grid

// --- CALCULATIONS ---
// Math for vertical-flat hexagons (points top/bottom)
R_in = slot_size / 2 / cos(30);                 // Inner radius for the cutout
x_stride = slot_size + wall_thickness;          // Horizontal distance between columns
R_out = (slot_size + wall_thickness)/2/cos(30); // Outer radius for the raised walls
y_stride = 1.5 * R_out;                         // Vertical distance between staggered rows

// Calculate the footprint of just the hex grid
hex_grid_width = wall_thickness + (cols * x_stride);
hex_grid_depth = wall_thickness + R_out + ((rows - 1) * y_stride) + R_out + wall_thickness;

// Add the 4mm margin to all four sides
total_width = hex_grid_width + (2 * edge_margin);
total_depth = hex_grid_depth + (2 * edge_margin);
total_height = slot_height + base_thickness;
raised_height = total_height + wall_protrusion; 

// Display final footprint size in the console
echo(str("Total Width (X): ", total_width, " mm"));
echo(str("Total Depth (Y): ", total_depth, " mm"));
echo(str("Max Height (Z): ", raised_height, " mm"));

// --- MODEL GENERATION ---
module raised_honeycomb_organizer() {
    difference() {
        
        // 1. POSITIVE GEOMETRY (Base + Raised Walls)
        union() {
            // The main flat rectangular base (now includes the 4mm frame)
            cube([total_width, total_depth, total_height]);
            
            // The raised outer walls of the hexagons
            for (r = [0 : rows - 1]) {
                current_cols = (r % 2 == 0) ? cols : cols - 1;
                
                for (c = [0 : current_cols - 1]) {
                    // X position shifted by the left edge margin
                    x_offset = (r % 2 == 0) ? 0 : (x_stride / 2);
                    x_pos = edge_margin + wall_thickness + (slot_size / 2) + (c * x_stride) + x_offset;
                    
                    // Y position shifted by the front edge margin
                    y_pos = edge_margin + wall_thickness + R_out + (r * y_stride);
                    
                    translate([x_pos, y_pos, 0])
                    rotate([0, 0, 30])
                        cylinder(r = R_out, h = raised_height, $fn = 6);
                }
            }
        }
        
        // 2. NEGATIVE GEOMETRY (Punching the holes)
        for (r = [0 : rows - 1]) {
            current_cols = (r % 2 == 0) ? cols : cols - 1;
            
            for (c = [0 : current_cols - 1]) {
                x_offset = (r % 2 == 0) ? 0 : (x_stride / 2);
                x_pos = edge_margin + wall_thickness + (slot_size / 2) + (c * x_stride) + x_offset;
                y_pos = edge_margin + wall_thickness + R_out + (r * y_stride);
                
                // Subtract the inner hexagon starting from the base floor
                translate([x_pos, y_pos, base_thickness])
                rotate([0, 0, 30])
                    cylinder(r = R_in, h = raised_height + 1, $fn = 6);
            }
        }
    }
}

// Render the final model
raised_honeycomb_organizer();
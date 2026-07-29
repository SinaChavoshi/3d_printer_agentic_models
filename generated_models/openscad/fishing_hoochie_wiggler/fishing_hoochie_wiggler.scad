// Hoochi Wiggler - Flattened Banana (Flat Sides for Multi-Color)
// Designed to be printed laying flat on its side to minimize filament waste.

$fn = 80; // High resolution for smooth curves

// --- Body Parameters ---
total_length = 38;       // Total length from the back rim to the flattened stem tip
body_width = 16;         // Increased by 5mm to provide extra material for side slicing
flat_side_width = 14;    // The final width after slicing the sides flat
body_height = 9;         // Starting height of the body
banana_bend = 14;        // Upward curve amount at the stem tip
stem_thickness = 1.5;    // How thin the flattened stem gets at the very front

// --- Cavity & Line Parameters ---
squid_cup_depth = 12;    
squid_cup_dia = 9.5;     

line_hole_dia = 2;       
line_exit_pos = 28.5;    // Exits 1/4 from the flattened tip (outside curve)

module wiggler() {
    difference() {
        // 1. The Main Banana Body (Now wider)
        union() {
            for(i=[0:39]) {
                t1 = i/40;
                t2 = (i+1)/40;
                
                y1 = t1 * total_length;
                z1 = pow(t1, 2) * banana_bend;
                y2 = t2 * total_length;
                z2 = pow(t2, 2) * banana_bend;
                
                w1 = body_width - (t1 * 1.5);
                w2 = body_width - (t2 * 1.5);
                
                h1 = body_height - (pow(t1, 3) * (body_height - stem_thickness));
                h2 = body_height - (pow(t2, 3) * (body_height - stem_thickness));
                
                hull() {
                    translate([0, y1, z1]) scale([w1, 1, h1]) sphere(d=1);
                    translate([0, y2, z2]) scale([w2, 1, h2]) sphere(d=1);
                }
            }
        }
        
        // 2. The Squid Head Receptacle (Negative Cone)
        translate([0, -2, 0])
            rotate([-90, 0, 0])
                cylinder(h=squid_cup_depth + 2, d1=squid_cup_dia, d2=line_hole_dia);
                
        // 3. The Line Through-Hole 
        hull() {
            translate([0, squid_cup_depth - 1, 0])
                sphere(d=line_hole_dia);
                
            exit_t = line_exit_pos / total_length;
            exit_z = (pow(exit_t, 2) * banana_bend);
            
            translate([0, line_exit_pos, exit_z - body_height])
                sphere(d=line_hole_dia * 1.2); 
        }
    }
}

// 4. Flat Slicer 
// Trims the back and the sides for perfect bed adhesion on its side
module print_ready_wiggler() {
    difference() {
        wiggler();
        
        // Slice the back end completely flat (Y=0)
        translate([-body_width, -5, -body_height * 2])
            cube([body_width * 2, 5, body_height * 4]);
            
        // Slice the RIGHT side flat
        translate([flat_side_width / 2, -10, -body_height * 2])
            cube([body_width, total_length + 20, body_height * 4]);
            
        // Slice the LEFT side flat
        translate([-body_width - (flat_side_width / 2), -10, -body_height * 2])
            cube([body_width, total_length + 20, body_height * 4]);
    }
}

// Orient for 3D printing
// Rotates the model 90 degrees so it lays perfectly flat on the sliced side.
translate([0, 0, flat_side_width / 2])
    rotate([0, 90, 0])
        print_ready_wiggler();
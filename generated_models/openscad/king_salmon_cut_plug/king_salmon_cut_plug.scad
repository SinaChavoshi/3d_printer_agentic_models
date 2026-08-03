// ==========================================
// AI-Optimized King Salmon Cut-Plug Lure Model
// ==========================================
// Resolution set high ($fn=120) for perfectly smooth 3D printing
$fn = 100; 

// --- CONFIGURABLE PARAMETERS ---

// 1. Overall Body Profile (Symmetrical / Round Cross-Section)
plug_length = 127;          // Total length in mm (127mm = 5 inches)

// The radii tuned to your preferred proportions
nose_radius = 11.5;         // Fatter radius near the front face
belly_radius = 13;          // Thickest part, positioned forward
mid_radius = 10;            // Gradual taper past the midway point
tail_radius = 1.5;          // Sharp, pointed tail tip


// 2. Concave Cut-Plug Face
cut_angle = 45;             
cut_offset_x = 15;          
concavity_radius = nose_radius * 1.15; 
concavity_depth = 6;        // Deeper, more aggressive scoop
oval_stretch_x = 2.25;                 
oval_stretch_y = 1.0;       

// Face Edge Roundover (Fillet)
edge_roundover = 1.5;       // Radius of the curve applied to the sharp outer lip (mm)


// 3. Eye Sockets (For 8mm 3D Eyes)
eye_diameter = 9.5;         // 8.2mm gives a tiny bit of clearance for an 8mm eye and glue
eye_pos_x = 37;             // Placed just behind the cut-plug face
eye_pos_z = 2;              // Positioned slightly above the centerline for a natural look
eye_flat_width = 21;        // The distance between the left and right flat surfaces (controls depth)


// 4. Bead Chain Through-Hole 
hole_diameter = 4.2;        
hole_entry_x = 18;          
hole_entry_z = -9;           
hole_exit_x = 50;           
hole_exit_z = 15;           // Exits diagonally UP through the back


// 5. Internal Rattle Chamber (The "Hollow Oval")
// Pause your 3D print right before this closes to drop in BBs/beads!
rattle_radius = 6.5;        
rattle_pos_x = 65;          
rattle_pos_z = 0;           


// --- ADVANCED GEOMETRY GENERATION ---

// Catmull-Rom Spline Math Functions (ensures perfectly smooth organic curves)
function cr_x(p0, p1, p2, p3, t) = 0.5 * ( (2 * p1[0]) + (-p0[0] + p2[0]) * t + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * (t * t) + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * (t * t * t) );
function cr_y(p0, p1, p2, p3, t) = 0.5 * ( (2 * p1[1]) + (-p0[1] + p2[1]) * t + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * (t * t) + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * (t * t * t) );
function catmull_rom_2d(p0, p1, p2, p3, t) = [ cr_x(p0,p1,p2,p3,t), cr_y(p0,p1,p2,p3,t) ];

// Control points for the curve [Radius, Length_Position]
p0 = [nose_radius, -plug_length * 0.3];     
p1 = [nose_radius, 0];                      
p2 = [belly_radius, plug_length * 0.25];    
p3 = [mid_radius, plug_length * 0.60];      
p4 = [tail_radius, plug_length];            
p5 = [0, plug_length * 1.2];                

// Build the array of 2D coordinates for the smooth curve
profile_points = concat(
    [[0, 0]], 
    [ for (t = [0 : 0.05 : 0.95]) catmull_rom_2d(p0, p1, p2, p3, t) ],
    [ for (t = [0 : 0.05 : 0.95]) catmull_rom_2d(p1, p2, p3, p4, t) ],
    [ for (t = [0 : 0.05 : 1.0]) catmull_rom_2d(p2, p3, p4, p5, t) ],
    [[0, plug_length]] 
);

module plug_body() {
    rotate([0, 90, 0]) 
    rotate_extrude($fn=120) {
        polygon(points = profile_points);
    }
}

module bead_chain_channel() {
    hull() {
        translate([hole_entry_x, 0, hole_entry_z]) sphere(d = hole_diameter);
        translate([hole_exit_x, 0, hole_exit_z]) sphere(d = hole_diameter);
    }
}

module concave_face_cutter() {
    translate([cut_offset_x, 0, 0])
        rotate([0, -90 - cut_angle, 0])
        union() {
            // 1. The Nose Remover
            translate([0, 0, 50]) cube([100, 100, 100], center=true);
            
            // 2. The Concave Scoop
            translate([0, 0, concavity_radius - concavity_depth]) 
                scale([oval_stretch_x, oval_stretch_y, 1])
                sphere(r = concavity_radius);
                
            // 3. The Edge Roundover (Fillet)
            scale([1 / cos(cut_angle), 1.0, 1.0]) 
                rotate_extrude() 
                translate([nose_radius - 0.5, 0, 0]) 
                circle(r = edge_roundover);
        }
}

module eye_sockets() {
    // Right side socket (positive Y)
    translate([eye_pos_x, eye_flat_width / 2, eye_pos_z])
        rotate([-90, 0, 0])
        cylinder(d=eye_diameter, h=20, $fn=60); // Extends outward to cut the surface
        
    // Left side socket (negative Y)
    translate([eye_pos_x, -eye_flat_width / 2, eye_pos_z])
        rotate([90, 0, 0])
        cylinder(d=eye_diameter, h=20, $fn=60); // Extends outward to cut the surface
}

module cut_plug() {
    difference() {
        plug_body();
        concave_face_cutter();
        bead_chain_channel();
        eye_sockets();
        translate([rattle_pos_x, 0, rattle_pos_z])
            scale([2, 1, 1]) sphere(r = rattle_radius);
    }
}

// Render the final flawless lure model
cut_plug();

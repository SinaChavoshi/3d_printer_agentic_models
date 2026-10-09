// Solid Heel, Support-Free Hollow High Heel Door Wedge
// Fixed: Restored adjustability parameters 
// Reference: image_3a1b85.jpg

/* [Primary Dimensions] */
length = 180;            
width = 57;              
height = 95;
wall_thickness = 5;      
toe_coverage = 85;       // Distance the top cover extends from the tip
vamp_h = 45;             // Height of the shoe opening
overhang_angle = 30;     // Internal bridging angle for support-free printing

/* [Heel Adjustments] */
heel_width = 40;         // Width of the heel block
heel_bottom_length = 30; // Length of the heel base
heel_top_length = 30;    // Length of the heel top rim
insole_depth = 14;       // Depth of the foot cavity inside the heel

/* [Profile Adjustments] */
ball_l = 80;             // Length of the flat front section before the arch
arch_l = 140;            // Location of the arch peak
arch_h = 35;             // Height of the arch underneath

/* [Calculated Coordinates] */
heel_f_b = length - heel_bottom_length;
heel_f_t = length - heel_top_length;

// Calculate overhang offset for support-free printing inside the toe
dz = vamp_h - 26; 
dx = dz * tan(overhang_angle);

// Outer side silhouette profile
points_side = [
    [0, 0],
    [ball_l, 0],
    [arch_l, arch_h],
    [heel_f_b, 0],
    [length, 0],
    [length, height],
    [heel_f_t, height],
    [toe_coverage, vamp_h],
    [0, 4] // Sharp 2mm toe tip
];

// Inner cavity side profile (Strictly routed to prevent bottom holes)
cavity_side = [
    [toe_coverage, vamp_h],
    // Parametric internal slope down from the opening
    [toe_coverage + dx, vamp_h - dz], 
    // Explicitly routed over the arch peak to guarantee no bottom holes
    [arch_l, arch_h + wall_thickness + 3],    
    // Connects into the solid heel block
    [heel_f_t + wall_thickness, height - insole_depth],
    [length - wall_thickness, height - insole_depth],
    // Vertical escapes to cleanly subtract from the top
    [length - wall_thickness, height + 10], 
    [toe_coverage, height + 10]            
];

// Outer top profile (controls Y-axis tapering)
points_top = [
    [0, width * 0.15],             
    [ball_l, width * 0.5],         // Widest point at the ball
    [heel_f_t, heel_width * 0.5],  // Tapering into the adjustable heel
    [length, heel_width * 0.5],    
    [length, -heel_width * 0.5],
    [heel_f_t, -heel_width * 0.5],
    [ball_l, -width * 0.5],
    [0, -width * 0.15]
];

module shoe_body() {
    intersection() {
        rotate([90, 0, 0])
            linear_extrude(height = width * 2, center = true)
            polygon(points_side);

        translate([0, 0, -10])
            linear_extrude(height = height * 2)
            polygon(points_top);
    }
}

module hollow_cavity() {
    intersection() {
        rotate([90, 0, 0])
            linear_extrude(height = width * 2, center = true)
            polygon(cavity_side);

        // Shrink the top profile to maintain wall thickness on the sides
        translate([0, 0, -10])
            linear_extrude(height = height * 2)
            offset(delta = -wall_thickness) polygon(points_top);
    }
}

// Execute final boolean subtraction
difference() {
    shoe_body();
    hollow_cavity();
}
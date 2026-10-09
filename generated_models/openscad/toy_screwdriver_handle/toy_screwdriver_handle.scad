// ====================================================================
// Parametric Kid-Friendly Toy Screwdriver Handle
// Designed for a 9 mm Square Bit
// ====================================================================

/* [Bit Socket Settings] */
bit_width             = 9.0;   // Nominal square bit width (mm)
bit_clearance         = 0.3;   // Extra clearance per side for 3D printing fit (0.25 - 0.4 mm)
bit_depth             = 25.0;  // Insertion depth of the square bit (mm)
lead_in_chamfer       = 2.0;   // Entrance funnel chamfer to guide the bit in (mm)

/* [Handle Dimensions] */
handle_length         = 80.0;  // Total handle length (ideal for kids: 75 - 85 mm)
pommel_diameter       = 32.0;  // Rear palm ball diameter (mm)
max_diameter          = 38.0;  // Main bulbous palm swell diameter (mm)
neck_diameter         = 24.0;  // Ergonomic finger waist diameter (mm)
collar_diameter       = 28.0;  // Safety collar to stop fingers slipping forward (mm)
nose_diameter         = 20.0;  // Front face diameter (mm)
base_flat_diameter    = 18.0;  // Flat bed-contact base for print stability (mm)

/* [Grip Flutes] */
num_flutes            = 6;     // Number of grip grooves around circumference
flute_radius          = 5.0;   // Curvature radius of each scallop flute (mm)
flute_cut_depth       = 2.0;   // Scallop cut depth into the handle body (mm)

/* [Optional Retention Magnet] */
include_magnet_pocket = true;  // Pocket at bottom of socket for an 8x3mm disc magnet
magnet_diameter       = 8.2;   // Diameter including tolerance (mm)
magnet_thickness      = 3.2;   // Thickness including tolerance (mm)

/* [Render Quality] */
$fn = 90;                      // 60-80 for preview; 100+ for final STL export (F6)


// ====================================================================
// Assembly
// ====================================================================

difference() {
    // 1. Solid ergonomic body
    handle_body();

    // 2. Tactile finger flutes
    grip_flutes();

    // 3. 9 mm square bit cavity & funnel guide
    bit_cavity();

    // 4. Optional disc magnet cavity
    if (include_magnet_pocket) {
        translate([0, 0, handle_length - bit_depth - magnet_thickness])
            cylinder(d = magnet_diameter, h = magnet_thickness + 0.1);
    }
}


// ====================================================================
// Geometry Modules
// ====================================================================

// Organic ergonomic handle body built via consecutive hull chaining
module handle_body() {
    // Bed contact base to rear pommel
    hull() {
        cylinder(d = base_flat_diameter, h = 1.0);
        translate([0, 0, 14]) sphere(d = pommel_diameter);
    }

    // Pommel to main palm swell
    hull() {
        translate([0, 0, 14]) sphere(d = pommel_diameter);
        translate([0, 0, 36]) sphere(d = max_diameter);
    }

    // Palm swell to finger waist
    hull() {
        translate([0, 0, 36]) sphere(d = max_diameter);
        translate([0, 0, 58]) sphere(d = neck_diameter);
    }

    // Finger waist to safety collar
    hull() {
        translate([0, 0, 58]) sphere(d = neck_diameter);
        translate([0, 0, 70]) cylinder(d = collar_diameter, h = 4.0);
    }

    // Safety collar to nose face
    hull() {
        translate([0, 0, 70]) cylinder(d = collar_diameter, h = 4.0);
        translate([0, 0, handle_length - 1.0]) cylinder(d = nose_diameter, h = 1.0);
    }
}

// Rounded tactile flutes along the palm section
module grip_flutes() {
    radial_dist = (max_diameter / 2) - flute_cut_depth + flute_radius;
    flute_span  = 26.0;

    for (i = [0 : num_flutes - 1]) {
        rotate([0, 0, i * (360 / num_flutes)])
        translate([radial_dist, 0, 24])
        hull() {
            sphere(r = flute_radius);
            cylinder(r = flute_radius, h = flute_span);
            translate([0, 0, flute_span]) sphere(r = flute_radius);
        }
    }
}

// 9 mm square bit socket with tapered lead-in guide
module bit_cavity() {
    cavity_side = bit_width + (2 * bit_clearance);

    // Main square shaft hole
    translate([-cavity_side / 2, -cavity_side / 2, handle_length - bit_depth])
        cube([cavity_side, cavity_side, bit_depth + 0.1]);

    // Tapered lead-in funnel at the nose
    translate([0, 0, handle_length - lead_in_chamfer])
        hull() {
            translate([-cavity_side / 2, -cavity_side / 2, 0])
                cube([cavity_side, cavity_side, 0.01]);
            translate([-(cavity_side / 2 + lead_in_chamfer), -(cavity_side / 2 + lead_in_chamfer), lead_in_chamfer + 0.2])
                cube([cavity_side + 2 * lead_in_chamfer, cavity_side + 2 * lead_in_chamfer, 0.01]);
        }
}


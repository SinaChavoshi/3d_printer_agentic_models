// 3.5" Puget Sound Coho Lure - Deep-Sunk Keel & Clean Tunnel
// Features: Compound Arch/Twist, Deep-Sunk Line Tube, V-Groove Scales, Flush Eye

$fn = 60; // Base curve resolution

// --- Toggles & Parameters ---
twist_angle = 60;       // Total twist from head to tail in degrees
enable_scales = false;  // Set to true for diamond scale pattern
eye_diameter = 9.0;     // Diameter of the recessed eye socket
eye_depth = 1.0;        // Depth of the flat-bottomed recess
tunnel_sink = 1.5;      // Sinks the tube into the blade (reduces belly protrusion)
render_steps = 40;      // Number of 3D slices (Increase to 80-100 before exporting STL)

length = 88.9;          
max_width = 17.0;       
blade_thickness = 2.2;  
cup_radius = 180.0;     

tunnel_outer = 5.5;
tunnel_inner = 2.4;
fillet_width = 12.0;    

// 1. Math Functions for Smooth Willow Leaf Taper
function clamp(v, min_v, max_v) = (v < min_v) ? min_v : ((v > max_v) ? max_v : v);
function get_width(z) = 
    let (t = clamp((z + length/2) / length, 0, 1))
    max(2, max_width * sin(180 * pow(t, 0.75))); 

// 2. 2D Cupped Cross Section (Blade + Sunk Keel)
module cross_section(w, shrink=0) {
    bt_outer = blade_thickness - shrink;
    to = tunnel_outer - shrink;
    
    if (bt_outer > 0 && to > 0) {
        union() {
            // Cupped Blade Arc
            intersection() {
                translate([0, -cup_radius + blade_thickness]) 
                difference() {
                    circle(r=cup_radius - shrink);
                    circle(r=cup_radius - blade_thickness);
                }
                translate([-w/2, -cup_radius]) square([w, cup_radius*2]);
            }
            // Sunk Keel / Line Tube Housing
            hull() {
                translate([0, -tunnel_outer/2 + tunnel_sink]) circle(d=to);
                translate([-min(w, fillet_width)/2, 0]) square([min(w, fillet_width), 0.1]);
            }
        }
    }
}

// 3. Compound 3D Helical/Arched Body Generator
module twisted_arched_body(shrink=0) {
    step_size = length / render_steps;
    for (i = [0 : render_steps - 1]) {
        z1 = -length/2 + i * step_size;
        z2 = z1 + step_size;
        w1 = get_width(z1);
        w2 = get_width(z2);
        
        a1 = (z1 / length) * twist_angle;
        a2 = (z2 / length) * twist_angle;
        
        theta1 = asin(z1 / cup_radius);
        y1 = cup_radius * cos(theta1) - cup_radius;
        
        theta2 = asin(z2 / cup_radius);
        y2 = cup_radius * cos(theta2) - cup_radius;
        
        hull() {
            translate([0, y1, z1]) 
            rotate([theta1, 0, 0]) 
            rotate([0, 0, a1])     
                linear_extrude(height=0.01, center=true) cross_section(w1, shrink);
                
            translate([0, y2, z2]) 
            rotate([theta2, 0, 0]) 
            rotate([0, 0, a2]) 
                linear_extrude(height=0.01, center=true) cross_section(w2, shrink);
        }
    }
}

// 4. Compound Arched & Sunk Internal Line Conduit
module twisted_arched_tunnel() {
    step_size = length / render_steps;
    // EXTENDED LOOP: Iterates from -1 to render_steps to punch cleanly through the ends
    for (i = [-1 : render_steps]) {
        z1 = -length/2 + i * step_size;
        z2 = z1 + step_size;
        
        a1 = (z1 / length) * twist_angle;
        a2 = (z2 / length) * twist_angle;
        
        theta1 = asin(z1 / cup_radius);
        y1 = cup_radius * cos(theta1) - cup_radius;
        
        theta2 = asin(z2 / cup_radius);
        y2 = cup_radius * cos(theta2) - cup_radius;
        
        hull() {
            translate([0, y1, z1]) 
            rotate([theta1, 0, 0]) 
            rotate([0, 0, a1]) 
                translate([0, -tunnel_outer/2 + tunnel_sink]) cylinder(d=tunnel_inner, h=0.01, $fn=20);
                
            translate([0, y2, z2]) 
            rotate([theta2, 0, 0]) 
            rotate([0, 0, a2]) 
                translate([0, -tunnel_outer/2 + tunnel_sink]) cylinder(d=tunnel_inner, h=0.01, $fn=20);
        }
    }
}

// 5. Diagonal Scale Texture Matrix
module scale_texture() {
    spacing = 3.5; 
    for (i = [-length*1.5 : spacing : length*1.5]) {
        translate([0, 0, i]) rotate([0, 45, 0]) cube([max_width*2, max_width*2, 0.6], center=true);
        translate([0, 0, i]) rotate([0, -45, 0]) cube([max_width*2, max_width*2, 0.6], center=true);
    }
}

// 6. Dynamic Eye Socket 
module eye_socket() {
    eye_z = -length/5;
    
    theta = asin(eye_z / cup_radius);
    eye_y = cup_radius * cos(theta) - cup_radius;
    a = (eye_z / length) * twist_angle;
    
    translate([0, eye_y, eye_z])
    rotate([theta, 0, 0])
    rotate([0, 0, a])
    translate([0, blade_thickness - eye_depth, 0])
    rotate([-90, 0, 0]) 
    cylinder(d=eye_diameter, h=10, $fn=40);
}

// Final Assembly
difference() {
    // Core Body Setup
    if (enable_scales) {
        union() {
            twisted_arched_body(0.4); 
            difference() {
                twisted_arched_body(0); 
                scale_texture();        
            }
        }
    } else {
        twisted_arched_body(0); 
    }
    
    // Subtract Internal Mechanics
    twisted_arched_tunnel();
    eye_socket();
    
    // Cut slightly inward on the trims to guarantee a flat entry/exit port
    translate([0, 0, length/2 + 4.8]) cube([max_width*2, max_width*2, 10], center=true);
    translate([0, 0, -length/2 - 4.8]) cube([max_width*2, max_width*2, 10], center=true);
}